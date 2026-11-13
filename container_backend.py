#!/usr/bin/env python3
"""Rootless Debian/Fedora package lifecycle for AppInstall. No host package writes."""
import configparser
import contextvars
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))

from package_meta import require_backend_tools

SPECS = {'deb': ('debian-apps', 'docker.io/library/debian:13'),
         'rpm': ('fedora-apps', 'registry.fedoraproject.org/fedora:44')}
ENV = dict(os.environ, DBX_CONTAINER_MANAGER='podman', LC_ALL='C')
PROGRESS = contextvars.ContextVar('appinstall_progress',default=None)


def state_dir():
    return Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'appinstall/containers'


def command(args, **kwargs):
    reporter = PROGRESS.get()
    if reporter and 'input' not in kwargs:
        process = subprocess.Popen(args, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
        chunks = []
        for line in iter(process.stdout.readline,b''):
            chunks.append(line); reporter(line.decode(errors='replace').rstrip())
        process.stdout.close()
        status = process.wait(); content = b''.join(chunks)
    else:
        result = subprocess.run(args, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
        status,content = result.returncode,result.stdout
    if status:
        raise RuntimeError(content.decode(errors='replace')[-12000:])
    return content


def archive(data, option, member=None):
    args = ['bsdtar', option, '-'] + ([member] if member else [])
    return command(args, input=data)


def deb_members(data):
    if not data.startswith(b'!<arch>\n'):
        raise ValueError('Invalid DEB archive')
    offset, members = 8, {}
    while offset < len(data):
        header = data[offset:offset+60]
        if len(header) != 60 or header[58:] != b'`\n':
            raise ValueError('Corrupt DEB member')
        size = int(header[48:58])
        name = header[:16].decode().strip().rstrip('/')
        offset += 60
        if size < 0 or offset+size > len(data):
            raise ValueError('Truncated DEB member')
        members[name] = data[offset:offset+size]
        offset += size + size % 2
    return members


def rpm_header(data, offset):
    if data[offset:offset+4] != b'\x8e\xad\xe8\x01':
        raise ValueError('Invalid RPM header')
    count, length = struct.unpack_from('>II', data, offset+8)
    start = offset+16+count*16
    end = start+length
    if count > 100000 or end > len(data):
        raise ValueError('Truncated RPM header')
    tags = {}
    for index in range(count):
        tag, kind, position, number = struct.unpack_from('>IIII', data, offset+16+index*16)
        if position >= length:
            raise ValueError('Invalid RPM offset')
        if kind in (6,8,9):
            strings = data[start+position:end].split(b'\0')
            tags[tag] = [value.decode(errors='replace') for value in strings[:number]]
    return tags, end


def inspect_package(file):
    path = Path(file).resolve(strict=True)
    kind = path.suffix.lower().lstrip('.')
    if kind not in SPECS:
        raise ValueError('Expected a .deb or .rpm file')
    require_backend_tools('bsdtar')
    data = path.read_bytes()
    if kind == 'deb':
        members = deb_members(data)
        if members.get('debian-binary') != b'2.0\n':
            raise ValueError('Unsupported DEB version')
        control = next((v for k,v in members.items() if k.startswith('control.tar')), None)
        payload = next((v for k,v in members.items() if k.startswith('data.tar')), None)
        if control is None or payload is None:
            raise ValueError('DEB has no control or payload archive')
        names = archive(control, '-tf').decode().splitlines()
        member = next((n for n in names if n.lstrip('./') == 'control'), None)
        if not member:
            raise ValueError('Missing DEB control metadata')
        fields = {}
        last = None
        for line in archive(control, '-xOf', member).decode().splitlines():
            if line.startswith(' ') and last:
                fields[last] += '\n'+line[1:]
            elif ':' in line:
                last,value = line.split(':',1); fields[last] = value.strip()
        name, version, arch = (fields.get(k,'') for k in ('Package','Version','Architecture'))
        description = fields.get('Description','')
        dependencies = fields.get('Pre-Depends','')+' '+fields.get('Depends','')
        maintainer = fields.get('Maintainer','')
        files = archive(payload, '-tf').decode().splitlines()
    else:
        if data[:4] != b'\xed\xab\xee\xdb':
            raise ValueError('Invalid RPM magic')
        _, end = rpm_header(data,96)
        tags, _ = rpm_header(data, (end+7)//8*8)
        get = lambda tag: tags.get(tag,[''])[0]
        name, version, arch = get(1000), get(1001)+'-'+get(1002), get(1022)
        description = get(1004)+'\n'+get(1005)
        dependencies = ', '.join(tags.get(1049,[]))
        maintainer = get(1015)
        files = archive(data,'-tf').decode().splitlines()
        payload = data
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+_.-]*',name) or not version or not arch:
        raise ValueError('Missing or invalid package metadata')
    host = platform.machine()
    allowed = {'x86_64': {'amd64','x86_64'}, 'aarch64': {'arm64','aarch64'}}.get(host,set()) | {'all','noarch'}
    if arch not in allowed:
        raise ValueError('Unsupported package architecture: '+arch)
    blocked = ('/lib/modules/', '/boot/', '/systemd/system/', '/init.d/', '/udev/rules.d/')
    if any(any(part in '/'+file.lstrip('./') for part in blocked) for file in files):
        raise ValueError('System packages, kernel modules, drivers and services are unsupported.')
    application_name = name
    icon_name = ""
    desktopfiles = [item for item in files if item.endswith('.desktop') and '/applications/' in item]
    if desktopfiles:
        try:
            preview = configparser.ConfigParser(interpolation=None,strict=False)
            preview.read_string(archive(payload,'-xOf',desktopfiles[0]).decode())
            application_name = preview['Desktop Entry'].get('Name',name)
            icon_name = preview['Desktop Entry'].get('Icon','')
        except (configparser.Error,KeyError,UnicodeError):
            pass
    container,image = SPECS[kind]
    info = dict(file=str(path),kind=kind,name=name,version=version,architecture=arch,
                description=description,dependencies=dependencies.strip(),maintainer=maintainer,
                application_name=application_name,container=container,image=image,sha256=hashlib.sha256(data).hexdigest())
    icons = [f for f in files if re.search(r'/(?:icons|pixmaps)/.*\.(?:png|svg|xpm)$','/'+f)]
    packages = state_dir()/'packages'; packages.mkdir(parents=True,exist_ok=True)
    staged = packages/(info['sha256']+'.'+kind)
    if not staged.exists(): staged.write_bytes(data)
    info['source'] = str(path); info['file'] = str(staged)
    info['icon'] = ''
    info['icon_name'] = icon_name
    if icons:
        cache = state_dir()/'previews'; cache.mkdir(parents=True,exist_ok=True)
        icon = cache/(info['sha256']+Path(icons[0]).suffix)
        imagebytes = archive(payload,'-xOf',icons[0])
        if len(imagebytes) < 8*1024*1024:
            icon.write_bytes(imagebytes); info['icon'] = str(icon)
    return info


def validate_apt_sources(sources):
    from urllib.parse import urlparse
    urls=[];continuation=False
    for raw in sources.splitlines():
        line=raw.split('#',1)[0].rstrip()
        if not line:
            continuation=False;continue
        stripped=line.strip()
        if stripped.lower().startswith('uris:'):
            urls.extend(stripped.split(':',1)[1].split());continuation=True
        elif raw[:1].isspace() and continuation:
            urls.extend(stripped.split())
        else:
            continuation=False
            if re.match(r'^deb(?:-src)?\s',stripped):
                fields=re.sub(r'\[[^]]*\]','',stripped).split()
                if len(fields)>1:urls.append(fields[1])
    if any(urlparse(url).scheme not in ('http','https') or urlparse(url).hostname not in ('deb.debian.org','security.debian.org') for url in urls):
        raise RuntimeError('Container contains an unknown APT repository; review it manually before continuing.')


class Engine:
    def __init__(self):
        if os.geteuid() == 0:
            raise RuntimeError('Run AppInstall as your normal user; containers must be rootless.')
        self.root = state_dir(); self.root.mkdir(parents=True,exist_ok=True)
        self.file = self.root/'registry.json'
        self.lock = (self.root/'operation.lock').open('w')
        fcntl.flock(self.lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.registry = json.loads(self.file.read_text()) if self.file.exists() else {}
        for record in self.registry.values():
            if record.get('status') in ('installing','removing'):
                record['status']='needs-repair'
        self.save()

    def close(self):
        self.lock.close()

    def save(self):
        temp = self.file.with_suffix('.new'); temp.write_text(json.dumps(self.registry,indent=2)); temp.replace(self.file)

    def enter(self, info, args):
        return command(['distrobox','enter','--name',info['container'],'--no-tty','--',*args])

    def ensure(self, info):
        require_backend_tools('podman', 'distrobox', 'bsdtar')
        if command(['podman','info','--format','{{.Host.Security.Rootless}}']).strip() != b'true':
            raise RuntimeError('Podman must run rootless.')
        found = subprocess.run(['podman','container','exists',info['container']],env=ENV).returncode
        ownership = self.root/(info['container']+'.json')
        if found not in (0,1):
            raise RuntimeError('Cannot query Podman containers.')
        if not found and not ownership.exists():
            raise RuntimeError('A container with the reserved AppInstall name already exists and is not managed by AppInstall.')
        if found:
            home = self.root/'homes'/info['container']; home.mkdir(parents=True,exist_ok=True)
            packages = self.root/'packages'; packages.mkdir(exist_ok=True)
            command(['distrobox','create','--yes','--no-entry','--name',info['container'],
                     '--image',info['image'],'--home',str(home),
                     '--volume',str(packages)+':'+str(packages)+':ro'])
            ownership.write_text(json.dumps(dict(image=info['image'])))
        # Initialize Distrobox without a host root prompt.
        self.enter(info,['true'])
        if info['kind']=='deb':
            paths = self.enter(info,['find','/etc/apt','-maxdepth','2','-type','f']).decode().splitlines()
            for path in paths:
                if path.endswith(('.list','.sources')):
                    sources = self.enter(info,['cat',path]).decode()
                    validate_apt_sources(sources)
        else:
            repos = self.enter(info,['dnf','repolist','--enabled']).decode()
            ids = [line.split()[0] for line in repos.splitlines() if line.strip() and not line.lower().startswith(('repo id','updating','repositories'))]
            if any(repo not in ('fedora','updates','fedora-cisco-openh264') for repo in ids):
                raise RuntimeError('Container contains unrecognized repositories. Review enabled repositories before continuing.\n'+repos)

    def key(self, info):
        return info['kind']+':'+info['name']

    def transaction(self, info):
        self.ensure(info)
        if info['kind'] == 'deb':
            self.enter(info,['sudo','apt-get','update'])
            return self.enter(info,['sudo','apt-get','--simulate','--no-remove','--reinstall','install',info['file']]).decode()
        previous = self.registry.get(self.key(info),{})
        operation = 'reinstall' if previous.get('version') == info['version'] else 'install'
        result = subprocess.run(['distrobox','enter','--name',info['container'],'--no-tty','--','sudo','dnf','--assumeno',operation,info['file']],env=ENV,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        text = result.stdout.decode(errors='replace')
        if result.returncode and 'Operation aborted' not in text and 'Is this ok' not in text:
            raise RuntimeError(text)
        return text

    def install(self, info, choose):
        if hashlib.sha256(Path(info['file']).read_bytes()).hexdigest() != info['sha256']:
            raise RuntimeError('Package changed after preview. Select it again.')
        key = self.key(info)
        previous = self.registry.get(key)
        self.registry[key] = dict(info,status='installing',exports=(previous or {}).get('exports',[]),icons=(previous or {}).get('icons',[]))
        self.save()
        try:
            if info['kind'] == 'deb':
                self.enter(info,['sudo','env','DEBIAN_FRONTEND=noninteractive','apt-get','--assume-yes','--no-remove','--reinstall','install',info['file']])
                files = self.enter(info,['dpkg-query','-L',info['name']]).decode().splitlines()
            else:
                self.enter(info,['sudo','dnf','--assumeyes','reinstall' if previous and previous.get('version') == info['version'] else 'install',info['file']])
                files = self.enter(info,['rpm','-ql',info['name']]).decode().splitlines()
            entries = self.visible_entries(info, files)
            selected = choose(entries) if entries else None
            exports = self.export(info,selected) if selected else []
            self.registry[key] = dict(info,status='installed',desktop=selected,candidates=entries,exports=exports,launch_verified=False)
            self.save()
            return self.registry[key]
        except BaseException:
            self.registry[key]['status'] = 'needs-repair'
            self.save()
            raise

    def visible_entries(self, info, files):
        entries = []
        for path in files:
            if not (path.startswith('/') and path.endswith('.desktop') and '/applications/' in path):
                continue
            parser = configparser.ConfigParser(interpolation=None,strict=False)
            try:
                parser.read_string(self.enter(info,['cat',path]).decode())
                meta = parser['Desktop Entry']
                if (meta.get('Type','Application') == 'Application' and
                    meta.get('NoDisplay','false').lower() != 'true' and
                    meta.get('Hidden','false').lower() != 'true' and meta.get('Exec')):
                    entries.append(path)
            except (configparser.Error,KeyError,UnicodeError):
                continue
        return entries

    def export(self, info, desktop):
        try:
            return self._export(info, desktop)
        except BaseException:
            key = self.key(info)
            if key in self.registry:
                self.registry[key]['status'] = 'needs-repair'
                self.save()
            raise

    def _export(self, info, desktop):
        apps = Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'applications'
        apps.mkdir(parents=True,exist_ok=True)
        # Supported Distrobox exporter prefixes its desktop ID with the container.
        predicted = apps/(info['container']+'-'+Path(desktop).name)
        owned = {p['path']:p['sha256'] for p in self.registry.get(self.key(info),{}).get('exports',[])}
        if predicted.exists() and (str(predicted) not in owned or hashlib.sha256(predicted.read_bytes()).hexdigest() != owned[str(predicted)]):
            raise RuntimeError('An unrelated or modified launcher already exists: '+str(predicted))
        before = {str(p):p.read_bytes() for p in apps.glob('*.desktop') if p.is_file()}
        # Preserve icon ownership as well: exporter icons may be shared by apps.
        iconroot = apps.parent/'icons'
        iconbefore = {str(p):p.read_bytes() for p in iconroot.rglob('*') if p.is_file()} if iconroot.exists() else {}
        try:
            self.enter(info,['distrobox-export','--app',desktop,'--export-label','none'])
        except BaseException:
            if predicted.exists():
                if str(predicted) in before:
                    predicted.write_bytes(before[str(predicted)])
                else:
                    predicted.unlink()
            raise
        changed = [p for p in apps.glob('*.desktop') if str(p) not in before or p.read_bytes() != before[str(p)]]
        exports = []
        for path in changed:
            content = path.read_bytes()
            if str(path) in before and str(path) not in owned:
                path.write_bytes(before[str(path)])
                raise RuntimeError('Exporter attempted to overwrite an unrelated launcher; it was restored.')
            exports.append(dict(path=str(path),sha256=hashlib.sha256(content).hexdigest()))
        iconchanges = []
        for icon in iconroot.rglob('*') if iconroot.exists() else []:
            if not icon.is_file(): continue
            content = icon.read_bytes()
            if str(icon) in iconbefore:
                if content != iconbefore[str(icon)]:
                    icon.write_bytes(iconbefore[str(icon)])
                continue
            iconchanges.append(dict(path=str(icon),sha256=hashlib.sha256(content).hexdigest()))
        if predicted.exists() and not exports:
            exports = [dict(path=str(predicted),sha256=hashlib.sha256(predicted.read_bytes()).hexdigest())]
        if not exports:
            raise RuntimeError('Distrobox did not produce an application launcher.')
        import launch_monitor
        for entry in exports:
            path=Path(entry['path'])
            if launch_monitor.desktop_values(path.read_text()).get('Exec'):
                spec=launch_monitor.wrap_desktop(self.key(info),path,info['kind'],container=info['container'],source_desktop=desktop,package=info['name'])
                entry['sha256']=spec['desktop_hash']
        previous_icons = self.registry.get(self.key(info),{}).get('icons',[])
        info['icons'] = list({item['path']:item for item in previous_icons+iconchanges}.values())
        key = self.key(info)
        if key in self.registry:
            self.registry[key].update(exports=exports,icons=info['icons'],desktop=desktop)
            self.save()
        return exports

    def uninstall(self,key, cleanup=()):
        cleanup = set(cleanup)
        info = self.registry[key]; info['status']='removing'; self.save()
        try:
            if info['kind'] == 'deb':
                self.enter(info,['sudo','apt-get','--assume-yes','remove',info['name']])
            else:
                self.enter(info,['sudo','dnf','--assumeyes','--setopt=clean_requirements_on_remove=False','remove',info['name']])
            for item in info.get('exports',[])+info.get('icons',[]):
                path = item['path']
                if any(path==other['path'] for otherkey,record in self.registry.items()
                       if otherkey!=key for other in record.get('icons',[])+record.get('exports',[])):
                    continue
                p = Path(path)
                if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == item['sha256']:
                    p.unlink()
            # Explicitly selected cleanup paths (launch history, etc.).
            for path in cleanup:
                p = Path(path)
                if p.is_dir():
                    import shutil; shutil.rmtree(p)
                elif p.is_file():
                    p.unlink()
            # Destroy the container when explicitly selected. Each app owns its
            # container, so this is safe only when the user chose it.
            if 'container' in cleanup:
                command(['distrobox','rm','--yes',info['container']],env=ENV)
            del self.registry[key]; self.save()
            import launch_monitor
            launch_monitor.update_registry(key,None)
        except BaseException:
            info['status']='needs-repair'; self.save(); raise

    def launch(self,key):
        info = self.registry[key]
        if not info.get('exports'):
            raise RuntimeError('This package has no exported graphical application.')
        import diagnostics_core
        return diagnostics_core.open_application(key)

    def container_health(self, key):
        """Health report for one registered container app (deb/rpm).

        Returns a dict with per-check booleans, an issues list and a healthy
        flag. Every check degrades gracefully when podman/distrobox are
        unavailable — a missing binary never crashes the report.
        """
        info = self.registry[key]
        checks = {
            'container_exists': False,
            'container_responsive': False,
            'exports_intact': True,
        }
        issues = []

        found = subprocess.run(['podman','container','exists',info['container']],
                               env=ENV).returncode
        checks['container_exists'] = (found == 0)
        if not checks['container_exists']:
            issues.append('Container '+info['container']+' does not exist')

        if checks['container_exists']:
            try:
                result = subprocess.run(['distrobox','enter','--name',info['container'],
                                         '--no-tty','--','true'],
                                        env=ENV, capture_output=True, timeout=30)
                checks['container_responsive'] = (result.returncode == 0)
            except (subprocess.TimeoutExpired, OSError):
                checks['container_responsive'] = False
            if not checks['container_responsive']:
                issues.append('Container '+info['container']+' is not responding')

        # Exports intact: every recorded launcher still exists and matches hash.
        for entry in info.get('exports', []):
            path = Path(entry['path'])
            if not path.is_file():
                checks['exports_intact'] = False
                issues.append('Exported launcher missing: '+entry['path'])
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                checks['exports_intact'] = False
                issues.append('Exported launcher modified: '+entry['path'])

        return dict(key=key, checks=checks, issues=issues, healthy=not issues)
