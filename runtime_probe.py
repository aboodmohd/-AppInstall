"""Read-only runtime probe, also sent verbatim into Distrobox via python -c."""
import json
import os
import platform
import re
import shutil
import subprocess
import sys


def inspect_runtime(request):
    package=request.get('package')
    if package and request.get('format') in ('deb','rpm'):
        args=['dpkg-query','-W','-f=${db:Status-Abbrev}',package] if request['format']=='deb' else ['rpm','-q','--queryformat','%{NAME}',package]
        try:
            installed=subprocess.run(args,capture_output=True,text=True,timeout=8)
            if installed.returncode or (request['format']=='deb' and not installed.stdout.startswith('ii')):
                return dict(category='dependency',detail='The recorded package is missing or is not fully installed. Reinstall it before launching.')
        except (OSError,subprocess.SubprocessError):
            pass
    cwd = request.get('cwd')
    argv = list(request['argv'])
    environment = dict(os.environ)
    if argv and os.path.basename(argv[0]) == 'env':
        argv.pop(0)
        while argv:
            if argv[0] == '--':
                argv.pop(0); break
            if argv[0] in ('-i','--ignore-environment'):
                argv.pop(0);environment.clear()
            elif argv[0].startswith('--unset='):
                environment.pop(argv.pop(0).split('=',1)[1],None)
            elif argv[0].startswith('--chdir='):
                cwd=argv.pop(0).split('=',1)[1]
            elif argv[0] in ('-C','--chdir') and len(argv)>1:
                argv.pop(0);cwd=argv.pop(0)
            elif argv[0] == '-u' and len(argv) > 1:
                argv.pop(0); environment.pop(argv.pop(0), None)
            elif re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', argv[0]):
                key, value = argv.pop(0).split('=', 1); environment[key] = value
            elif argv[0].startswith('-'):
                return dict(notes=['An env option could not be checked statically; runtime output will be monitored.'])
            else:
                break
    if not argv:
        return dict(category='launcher', detail='The launcher does not contain an executable.')
    for key in request.get('required_env', []):
        if not environment.get(key):
            return dict(category='environment', detail='Required environment variable is not set: '+key)
    path = argv[0]
    if '/' not in path:
        path = shutil.which(path, path=environment.get('PATH'))
    if not path or not os.path.isfile(path):
        return dict(category='executable', detail='The application executable does not exist: '+str(argv[0]))
    if not os.access(path, os.X_OK):
        return dict(category='permission', detail='The application executable is not executable: '+str(path))
    if cwd and not os.path.isdir(cwd):
        return dict(category='launcher', detail='The launcher working directory does not exist: '+str(cwd))
    notes = []
    try:
        with open(path, 'rb') as file:
            header = file.read(64)
        if header[:4] == b'\x7fELF':
            endian = 'little' if header[5] == 1 else 'big'
            machine = int.from_bytes(header[18:20], endian)
            expected = {'x86_64':62,'aarch64':183}.get(platform.machine())
            if expected and machine != expected:
                return dict(category='architecture', detail='The executable architecture does not match this environment.')
            if shutil.which('readelf'):
                result = subprocess.run(['readelf', '-d', path], capture_output=True, text=True, timeout=8)
                needed = re.findall(r'\(NEEDED\).*?\[(.*?)\]', result.stdout)
                paths = re.findall(r'\((?:RUNPATH|RPATH)\).*?\[(.*?)\]', result.stdout)
                origin = os.path.dirname(os.path.realpath(path))
                search = environment.get('LD_LIBRARY_PATH','').split(':')
                for group in paths:
                    search += group.replace('${ORIGIN}', origin).replace('$ORIGIN', origin).split(':')
                search += ['/lib','/lib64','/usr/lib','/usr/lib64',
                           '/lib/x86_64-linux-gnu','/usr/lib/x86_64-linux-gnu',
                           '/lib/aarch64-linux-gnu','/usr/lib/aarch64-linux-gnu']
                cache = subprocess.run(['ldconfig','-p'], capture_output=True, text=True, timeout=8).stdout if shutil.which('ldconfig') else ''
                available = set(re.findall(r'^\s*(\S+)\s+\(', cache, re.M))
                missing = [lib for lib in needed if lib not in available and not any(folder and os.path.isfile(os.path.join(folder, lib)) for folder in search)]
                if missing:
                    return dict(category='dependency', detail='Required shared libraries were not found: '+', '.join(missing), libraries=missing)
            else:
                notes.append('Static shared-library inspection unavailable; runtime output will still be monitored.')
    except (OSError, subprocess.SubprocessError):
        notes.append('Static inspection was inconclusive; runtime output will be monitored.')
    return dict(notes=notes)


if __name__ == '__main__':
    try:
        print(json.dumps(inspect_runtime(json.loads(sys.argv[1]))))
    except Exception:
        print(json.dumps(dict(notes=['Static inspection was inconclusive.'])))
