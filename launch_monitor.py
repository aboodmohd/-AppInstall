#!/usr/bin/env python3
"""One monitored entry point for AppInstall-owned launchers; never runs a shell."""
import argparse
import configparser
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
from urllib.parse import unquote, urlparse

STARTUP_SECONDS = 12
LOG_BYTES = 128*1024
HISTORY = 8
MAX_OUTPUT_LINE = 16384


def data_root():
    return Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'appinstall'


def state_root():
    path = Path(os.environ.get('XDG_STATE_HOME', Path.home()/'.local/state'))/'appinstall'
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    fd = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        json.dump(value, file, indent=2)
        file.flush(); os.fsync(file.fileno())
    temporary.replace(path)


def registry():
    path = data_root()/'launchers.json'
    return json.loads(path.read_text()) if path.exists() else {}


def update_registry(key, value=None):
    root = data_root(); root.mkdir(parents=True, exist_ok=True)
    with (root/'launchers.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = registry()
        if value is None:
            records.pop(key, None)
        else:
            records[key] = value
        atomic_json(root/'launchers.json', records)


def desktop_values(text, section='Desktop Entry'):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str; parser.read_string(text)
    return dict(parser[section])


def desktop_quote(value, fields=False):
    # Two escaping layers: desktop-value escaping, then quoted Exec argument.
    result = str(value).replace('\\','\\\\')
    for char in ('"','`','$'):
        result = result.replace(char,'\\'+char)
    result=result.replace('\\','\\\\').replace('\n',r'\n').replace('\t',r'\t').replace('\r',r'\r')
    return '"'+(result if fields else result.replace('%','%%'))+'"'


def decode_value(value):
    return re.sub(r'\\([sntr\\])', lambda match: {'s':' ','n':'\n','t':'\t','r':'\r','\\':'\\'}[match[1]], value)


def expand_exec(value, files, spec, action=None):
    tokens = [re.sub(r'\\([$`])',r'\1',token) for token in shlex.split(decode_value(value), posix=True)]
    result = []
    for token in tokens:
        if token in ('%U','%F','%u','%f'):
            values = list(files)
            if token in ('%F','%f'):
                values = [unquote(urlparse(item).path) if item.startswith('file://') else item for item in values]
            result.extend(values[:1] if token in ('%u','%f') else values)
        elif token == '%i':
            if spec.get('icon'): result.extend(['--icon',spec['icon']])
        elif token in ('%d','%D','%n','%N','%v','%m'):
            continue
        else:
            def field(match):
                code = match[1]
                if code == '%': return '%'
                if code == 'c': return spec['name']
                if code == 'k': return spec.get('source_desktop', spec['desktop'])
                raise ValueError('Unsupported or embedded desktop field code: %'+code)
            result.append(re.sub(r'%(.)', field, token))
    if not result or not result[0] or result[0].startswith('-'):
        raise ValueError('The launcher does not contain a valid command.')
    return result


def wrap_desktop(key, path, format, **extra):
    path = Path(path)
    original = path.read_text()
    meta = desktop_values(original)
    old = registry().get(key)
    if meta.get('X-AppInstall-LaunchID') == key:
        if not old: raise RuntimeError('The monitored launcher has lost its registry record.')
        return old
    actions = {}
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str; parser.read_string(original)
    for section in parser.sections():
        if section.startswith('Desktop Action ') and parser.has_option(section,'Exec'):
            actions[section[15:]] = parser.get(section,'Exec')
    override=extra.pop('command_override',None)
    cwd_override=extra.pop('cwd_override',None)
    spec = dict(key=key, name=meta.get('Name',key), format=format, desktop=str(path),
                original_text=original, command=meta.get('Exec',''), cwd=decode_value(meta.get('Path','')),
                icon=meta.get('Icon',''), terminal=meta.get('Terminal','false').lower()=='true', actions=actions, **extra)
    if override is not None: spec['command']=override
    if cwd_override is not None:spec['cwd']=cwd_override
    # Registration is metadata-only; invalid commands are diagnosed at launch.
    backup = state_root()/'launcher-backups'/hashlib.sha256(key.encode()).hexdigest()
    backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not backup.exists():
        fd = os.open(backup, os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as file: file.write(original)
    spec['backup'] = str(backup)
    update_registry(key,spec)
    rewrite_launcher(spec)
    return registry()[key]


def rewrite_launcher(spec):
    path = Path(spec['desktop'])
    if path.exists():
        current = desktop_values(path.read_text())
        current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if current_hash not in (spec.get('desktop_hash'),hashlib.sha256(spec['original_text'].encode()).hexdigest()):
            raise RuntimeError('This launcher was modified outside AppInstall. It has not been overwritten.')
    lines, section = [], ''
    for line in spec['original_text'].splitlines():
        if line.startswith('['): section = line[1:-1]
        if section == 'Desktop Entry' and line.startswith(('Path=','DBusActivatable=','X-AppInstall-LaunchID=')):
            continue
        if line.startswith('Exec=') and (section=='Desktop Entry' or section.startswith('Desktop Action ')):
            action = ' --action '+desktop_quote(section[15:]) if section.startswith('Desktop Action ') else ''
            line='Exec='+desktop_quote(sys.executable)+' '+desktop_quote(Path(__file__).resolve())+' --launch '+desktop_quote(spec['key'])+action+' -- %U'
        lines.append(line)
        if line == '[Desktop Entry]':
            lines.extend(['X-AppInstall-LaunchID='+spec['key'],'DBusActivatable=false'])
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text('\n'.join(lines)+'\n'); temporary.replace(path)
    spec['desktop_hash']=hashlib.sha256(path.read_bytes()).hexdigest()
    update_registry(spec['key'],spec)


def redact(text, secrets=()):
    text = re.sub(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))','',str(text))
    for secret in sorted(set(secrets),key=len,reverse=True):
        if len(secret)>=4: text=text.replace(secret,'[REDACTED]')
    text=re.sub(r'(?i)\b(?:ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b','[REDACTED]',text)
    text=re.sub(r'(?i)(bearer\s+)[A-Za-z0-9_.+/=-]+',r'\1[REDACTED]',text)
    text=re.sub(r'''(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|credential|token)["']?\s*[:=]\s*)(["']).*?\2''',r'\1[REDACTED]',text)
    text=re.sub(r'(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|authorization|secret|credential|token)["\x27]?\s*[:=]\s*["\x27]?)[^\s,"\x27;&]+',r'\1[REDACTED]',text)
    text=re.sub(r'(https?://)[^/@\s]+:[^/@\s]+@',r'\1[REDACTED]@',text)
    text=re.sub(r'(https?://[^\s?#]+)\?[^\s#]*',r'\1?[REDACTED]',text)
    return text


def private_values(argv=()):
    values=[value for key,value in os.environ.items() if re.search(r'(?i)token|secret|password|credential|api.?key|authorization',key)]
    for i,token in enumerate(argv):
        if re.search(r'(?i)(?:token|secret|password|api.?key|authorization)',token):
            if '=' in token: values.append(token.split('=',1)[1])
            elif i+1<len(argv): values.append(argv[i+1])
    return values


class SafeLog:
    def __init__(self,path,secrets=()):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.secrets=secrets; self.content=''
        fd=os.open(self.path,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600);os.close(fd)
        self.last=time.monotonic()
    def _persist(self):
        self.path.write_text(self.content)
        self.last=time.monotonic()
    def add(self,text):
        if not self.path.exists(): return
        self.content += redact(text,self.secrets)+'\n'
        content=self.content.encode()[-LOG_BYTES:]
        self.content=content.decode(errors='ignore')
        if time.monotonic()-self.last>=0.5: self._persist()
    def flush(self):
        if not self.path.exists(): return
        self._persist()


def failure(category,detail,**extra):
    return dict(category=category,detail=detail,**extra)


def classify(output, code=None, phase='application'):
    if phase=='container': return failure('container','The container could not start. Review the container output and retry startup.')
    match=re.search(r'error while loading shared libraries:\s*([^\s:]+)',output,re.I)
    if match:
        if re.search(r'permission denied',output,re.I):return failure('permission','A required library could not be accessed because permission was denied.')
        if re.search(r'wrong ELF class|ELFCLASS|invalid ELF',output,re.I):return failure('architecture','A required library has an incompatible binary format.')
        return failure('dependency','A required shared library is missing: '+match[1],libraries=[match[1]])
    match=re.search(r'(?:port\s+|address[^\n]*?:)(\d{2,5})[^\n]{0,180}(?:already in use|EADDRINUSE)',output,re.I)
    if not match: match=re.search(r'EADDRINUSE[^\n]*?[: ](\d{2,5})',output,re.I)
    if match: return failure('port','Port '+match[1]+' is already in use.',port=int(match[1]))
    if code in (126,127): return failure('executable','The executable could not be started. Review the command and permissions.')
    if code is not None and code!=0: return failure('crash','The application exited unexpectedly during startup.')
    return None


def checked(args, timeout=60):
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout,env=dict(os.environ,DBX_CONTAINER_MANAGER='podman'))
    if result.returncode: raise RuntimeError(result.stdout.decode(errors='replace')[-8192:])
    return result.stdout.decode(errors='replace')


def port_observations(spec):
    ports=list(spec.get('documented_ports',[]))
    file=data_root()/'containers/registry.json'
    if spec.get('container') and file.exists():
        try:
            info=json.loads(file.read_text()).get(spec['key'],{})
            for repair in info.get('runtime_repairs',[]):
                if 'port' in str(repair.get('setting','')).lower():ports.append(repair.get('value'))
        except (OSError,ValueError,AttributeError):pass
    notes=[]
    if not shutil.which('ss'):return notes
    for port in sorted({value for value in ports if isinstance(value,int) and 1<=value<=65535}):
        try:
            output=checked(['ss','-ltn','sport = :'+str(port)],5)
            occupied=len(output.strip().splitlines())>1
            notes.append('Configured port '+str(port)+(' is already listening. It may be the application’s own reusable service; no conflict is assumed.' if occupied else ' has no listener at this check.'))
        except (OSError,RuntimeError,subprocess.SubprocessError):notes.append('Configured port could not be inspected.')
    return notes


def preflight(spec, argv):
    environment=dict(os.environ)
    cwd=spec.get('cwd') or None
    if spec['format']=='appimage':
        environment['APPIMAGELAUNCHER_DISABLE']='1'
        manifest=json.loads(Path(spec['manifest']).read_text())
        if manifest.get('fallback'):
            environment.update(APPDIR=manifest['fallback'],APPIMAGE=manifest['target'])
            cwd=cwd or manifest['fallback']
    container=spec.get('container')
    if container:
        if not shutil.which('podman') or not shutil.which('distrobox'):
            return failure('container','Podman or Distrobox is missing.'),None
        try:
            result=subprocess.run(['podman','container','exists',container],capture_output=True,timeout=15)
            if result.returncode:
                return failure('container','The '+container+' container is missing or cannot be accessed.'),None
            checked(['distrobox','enter','--name',container,'--no-tty','--','true'],120)
        except (OSError,RuntimeError,subprocess.TimeoutExpired) as error:
            return failure('container','The '+container+' container could not start.',technical=str(error)),None
    probe=Path(__file__).with_name('runtime_probe.py')
    request=dict(argv=argv,cwd=cwd,required_env=spec.get('required_env',[]),format=spec['format'],package=spec.get('package'))
    if container:
        try:
            text=checked(['distrobox','enter','--name',container,'--no-tty','--','python3','-c',probe.read_text(),json.dumps(request)],30)
            result=json.loads(text.splitlines()[-1])
        except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired):
            result=dict(notes=['Static checks unavailable; application output will be monitored.'])
        if result.get('category'): return result,None
        prefix=['distrobox','enter','--name',container,'--no-tty','--']
        if cwd: prefix += ['env','--chdir='+cwd]
        return None,(prefix+argv,None,dict(environment,DBX_CONTAINER_MANAGER='podman'),result.get('notes',[])+port_observations(spec))
    # Flatpak exports invoke flatpak itself; check runtime errors from flatpak output.
    import runtime_probe
    result=runtime_probe.inspect_runtime(request)
    if result.get('category'): return result,None
    return None,(argv,cwd,environment,result.get('notes',[])+port_observations(spec))


def new_attempt(spec):
    directory=state_root()/'launches'/hashlib.sha256(spec['key'].encode()).hexdigest()[:20]
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    attempt=dict(id=uuid.uuid4().hex,key=spec['key'],name=spec['name'],format=spec['format'],container=spec.get('container'),started=now,status='checking',error=None,exit_code=None)
    path=directory/(attempt['id']+'.json'); attempt['log']=str(path.with_suffix('.log'));attempt['file']=str(path)
    previous=history(spec['key'])
    for item in previous[HISTORY-1:]:
        old=Path(item['file']);old.with_suffix('.log').unlink(missing_ok=True);old.unlink(missing_ok=True)
    atomic_json(path,attempt)
    return attempt


def error_text(spec,error):
    tips={'dependency':'Review the missing library. A known official-repository repair may be available in Application Diagnostics.',
          'port':'Use Application Diagnostics to inspect the port owner. Do not stop other processes without checking them.',
          'container':'Check rootless Podman and the named container. Retry startup or review its logs.',
          'launcher':'Repair the managed launcher from Application Diagnostics.',
          'executable':'Check whether the application is still installed; repair its launcher or reinstall it.',
          'permission':'Check executable permissions or reinstall the package.',
          'architecture':'Install a package built for this computer’s architecture.',
          'environment':'Review the required environment setting for this application.',
          'crash':'View Logs for startup output. The exact cause may require application-specific troubleshooting.'}
    return spec['name']+' — '+error['category']+'\n'+error['detail']+'\n'+tips.get(error['category'],'View Logs for more information.')


def deliver_error(spec,attempt):
    text=error_text(spec,attempt['error'])
    delivered=False
    if shutil.which('notify-send'):
        try:
            result=subprocess.run(['notify-send','--print-id','--app-name=AppInstall','--urgency=critical','AppInstall launch failed',text],capture_output=True,timeout=5)
            delivered=result.returncode==0
            if result.stdout and result.stdout.strip().isdigit():attempt['notification_id']=int(result.stdout.strip())
        except (OSError,subprocess.TimeoutExpired): pass
    ui=Path(__file__).with_name('diagnostics_ui.py')
    import importlib.util
    if ui.exists() and importlib.util.find_spec('PySide6'):
        try:
            subprocess.Popen([sys.executable,str(ui),'--error',attempt['file']],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            delivered=True
        except OSError: pass
    if not delivered:
        for tool,args in [('kdialog',['--error']),('zenity',['--error','--text'])]:
            if shutil.which(tool):
                try: subprocess.Popen([tool,*args,text]);delivered=True;break
                except OSError: pass
    if not delivered:print(text+'\nLog: '+attempt['log'],file=sys.stderr)
    return delivered


def monitor(spec, files=(), action=None, notify=True, startup=STARTUP_SECONDS):
    attempt=new_attempt(spec); log=SafeLog(attempt['log'])
    start=time.monotonic()
    def record():
        if Path(attempt['file']).exists():atomic_json(attempt['file'],attempt)
    def fail(error,technical=''):
        cleaned={key:redact(value,log.secrets) if isinstance(value,str) else value for key,value in error.items()}
        attempt.update(status='failed',error=cleaned,technical=redact(technical,log.secrets)[-8192:])
        log.add(error_text(spec,cleaned));log.flush();record()
        if notify:
            attempt['notification_requested']=deliver_error(spec,attempt);record()
        return attempt
    try:
        if spec.get('launch_error'):return fail(spec['launch_error'])
        if not Path(spec['desktop']).is_file():
            return fail(failure('launcher','The managed desktop entry is missing.'))
        value=spec.get('actions',{}).get(action) if action else spec['command']
        if value is None: raise ValueError('The requested desktop action does not exist.')
        argv=expand_exec(value,files,spec,action)
        # Container records retain the Distrobox-exported command. The wrapper
        # supplies that same backend itself after verifying container startup.
        if spec.get('container'):
            marker=argv.index('--') if '--' in argv else -1
            if Path(argv[0]).name not in ('distrobox-enter','distrobox') or marker<0:
                return fail(failure('launcher','The container launcher does not contain a valid Distrobox command.'))
            argv=argv[marker+1:]
        log.secrets=private_values(argv)
        error,prepared=preflight(spec,argv)
        if error: return fail(error,error.get('technical',''))
        command,cwd,environment,notes=prepared
        attempt['checks']=[redact(note,log.secrets) for note in notes]
        for note in attempt['checks']:log.add(note)
        log.add('Runtime checks completed. Starting the application; window availability is not inferred.')
        terminal=spec.get('terminal',False)
        process=subprocess.Popen(command,cwd=cwd,env=environment,stdout=None if terminal else subprocess.PIPE,stderr=subprocess.PIPE if terminal else subprocess.STDOUT,stdin=None if terminal else subprocess.DEVNULL)
        start=time.monotonic()
        attempt.update(status='starting',pid=process.pid);record()
        lines=queue.Queue(maxsize=256)
        def reader():
            truncated=False
            stream=process.stderr if terminal else process.stdout
            for raw in iter(lambda:stream.readline(MAX_OUTPUT_LINE+1),b''):
                if len(raw)>MAX_OUTPUT_LINE or truncated:
                    truncated=not raw.endswith(b'\n')
                    if not truncated:
                        try: lines.put_nowait('[Long output line omitted for privacy]')
                        except queue.Full: pass
                    continue
                try: lines.put_nowait(raw.decode(errors='replace').rstrip())
                except queue.Full: pass
            stream.close()
        thread=threading.Thread(target=reader,daemon=True);thread.start()
        evidence='';reported=False;exit_seen=None
        while True:
            try:
                line=lines.get(timeout=.1);safe=redact(line,log.secrets);log.add(safe)
                if time.monotonic()-start <= startup:
                    evidence=(evidence+'\n'+safe)[-LOG_BYTES:]
            except queue.Empty: pass
            code=process.poll()
            elapsed=time.monotonic()-start
            if code is not None and exit_seen is None: exit_seen=time.monotonic()
            if code is not None and ((not thread.is_alive() and lines.empty()) or time.monotonic()-exit_seen>1.5):
                attempt['exit_code']=code
                error=classify(evidence,code if elapsed<=startup else None)
                if error: return fail(error,'Exit status: '+str(code)+'\n'+evidence)
                attempt['status']='detached_or_exited_unverified' if code==0 else 'exited_after_startup_unverified'
                log.flush();record();return attempt
            if elapsed>startup and not reported:
                attempt['status']='running_unverified';log.flush();record();reported=True
    except PermissionError as error:
        return fail(failure('permission','A file or executable could not be accessed.'),str(error))
    except (OSError,ValueError,KeyError,TypeError,ImportError,configparser.Error,subprocess.SubprocessError) as error:
        return fail(failure('launcher','The application launcher could not be started.'),str(error))


def history(key):
    directory=state_root()/'launches'/hashlib.sha256(key.encode()).hexdigest()[:20]
    attempts=[]
    for path in directory.glob('*.json'):
        try:attempts.append(json.loads(path.read_text()))
        except (OSError,ValueError):continue
    return sorted(attempts,key=lambda item:item.get('started',''),reverse=True)


def latest(key):
    attempts=history(key)
    return attempts[0] if attempts else None


def wrap_appimage(path, manifest):
    info=json.loads(Path(manifest).read_text())
    ident=Path(manifest).stem
    target=str(Path(info.get('fallback',''))/'AppRun') if info.get('fallback') else info['target']
    if info.get('desktop_exec'):
        tokens=shlex.split(decode_value(info['desktop_exec']))
        index=0
        if tokens and Path(tokens[0]).name=='env':
            index=1
            while index<len(tokens):
                token=tokens[index]
                if token=='--':index+=1;break
                if token in ('-u','-C','--unset','--chdir'):index+=2;continue
                if token.startswith('-') or re.match(r'^[A-Za-z_][A-Za-z0-9_]*=',token):index+=1;continue
                break
        if index>=len(tokens):raise ValueError('The AppImage desktop command has no executable.')
        tokens[index]=target
        command=' '.join(desktop_quote(token,fields=(position!=index)) for position,token in enumerate(tokens))
    else:
        tokens=info.get('desktop_args',info['args']+['%U'])
        command=desktop_quote(target)+' '+ ' '.join(desktop_quote(token,fields=True) for token in tokens)
    return wrap_desktop('appimage:'+ident,path,'appimage',manifest=str(manifest),command_override=command,cwd_override=info.get('working_directory',''))


def synchronize():
    """Adopt only launchers backed by existing AppInstall ownership evidence."""
    errors=[]
    container_file=data_root()/'containers/registry.json'
    if container_file.exists():
        lock=(container_file.parent/'operation.lock').open('a')
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            records=json.loads(container_file.read_text())
            for key,info in records.items():
                for entry in info.get('exports',[]):
                    path=Path(entry['path'])
                    if not path.is_file():continue
                    if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:continue
                    try:
                        spec=wrap_desktop(key,path,info['kind'],container=info['container'],source_desktop=info.get('desktop',''),package=info['name'])
                        entry['sha256']=spec['desktop_hash']
                    except Exception as error:errors.append(str(error))
            atomic_json(container_file,records)
        except BlockingIOError:
            errors.append('Container launchers were not migrated because another package operation is active. Close it and run the user installer again.')
        finally:
            lock.close()
    apps=data_root().parent/'applications'
    for path in apps.glob('*.desktop'):
        try:
            meta=desktop_values(path.read_text())
            if meta.get('X-AppInstall-Manifest'):
                wrap_appimage(path,meta['X-AppInstall-Manifest'])
        except (OSError,ValueError,KeyError,configparser.Error) as error:errors.append(str(error))
    return errors


def restore_launchers():
    """Explicit rollback: restore only files still matching our managed hash."""
    restored=[];skipped=[]
    container_file=data_root()/'containers/registry.json'
    lock=None
    try:
        if container_file.exists():
            lock=(container_file.parent/'operation.lock').open('a')
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        containers=json.loads(container_file.read_text()) if container_file.exists() else {}
        for key,spec in registry().items():
            path=Path(spec['desktop'])
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=spec.get('desktop_hash'):
                skipped.append(spec['name']);continue
            path.parent.mkdir(parents=True,exist_ok=True)
            temp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
            temp.write_text(spec['original_text']);temp.replace(path)
            for record in containers.values():
                for entry in record.get('exports',[]):
                    if entry['path']==str(path):entry['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            update_registry(key,None);restored.append(spec['name'])
        if container_file.exists():atomic_json(container_file,containers)
    finally:
        if lock:lock.close()
    return dict(restored=restored,skipped_modified=skipped)


def adopt_flatpak(appid):
    apps=data_root().parent/'applications'
    path=apps/(appid+'.desktop')
    if not path.exists(): return
    meta=desktop_values(path.read_text())
    if meta.get('X-AppInstall-LaunchID'): return
    argv=shlex.split(decode_value(meta.get('Exec','')))
    if not argv or Path(argv[0]).name!='flatpak' or appid not in argv:
        raise RuntimeError('The existing launcher is not the expected Flatpak entry.')
    if path.is_symlink():
        text=path.read_text();path.unlink();path.write_text(text)
    wrap_desktop('flatpak:'+appid,path,'flatpak',appid=appid)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--restore-launchers',action='store_true');parser.add_argument('--forget');parser.add_argument('--launch');parser.add_argument('--action');parser.add_argument('--adopt-flatpak')
    parser.add_argument('files',nargs='*');args=parser.parse_args()
    if args.restore_launchers:
        if not sys.stdin.isatty() or input('Restore AppInstall-managed launchers to their original commands? [y/N] ').lower()!='y':raise SystemExit('No launchers were changed.')
        print(json.dumps(restore_launchers(),indent=2))
    elif args.forget:update_registry(args.forget,None)
    elif args.adopt_flatpak: adopt_flatpak(args.adopt_flatpak)
    else:
        try:
            records=registry();spec=records.get(args.launch)
        except (OSError,ValueError):
            spec=None
        if spec is None:
            spec=dict(key=args.launch or 'unknown',name='Application',format='unknown',desktop='',command='',launch_error=failure('launcher','The launcher registry entry is missing or unreadable. Restore or reinstall this managed launcher.'))
        monitor(spec,args.files,args.action)
