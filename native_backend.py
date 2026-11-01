#!/usr/bin/env python3
"""Native package inspection and installation. Never converts foreign packages."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def output(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def backend(kind):
    release = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            release[key] = value.strip('"')
    family = set((release.get('ID','')+' '+release.get('ID_LIKE','')).split())
    if kind == 'deb' and family & {'ubuntu','debian'}:
        return 'apt-get'
    if kind == 'rpm' and 'fedora' in family:
        return 'dnf'
    if kind == 'rpm' and family & {'opensuse','opensuse-leap','opensuse-tumbleweed','suse'}:
        return 'zypper'
    raise RuntimeError('This package is not supported on '+release.get('NAME','this distribution')+'. Download an AppImage or Flatpak instead.')


def inspect(file):
    file = str(Path(file).resolve(strict=True))
    kind = Path(file).suffix.lower().lstrip('.')
    manager = backend(kind)
    if not shutil.which(manager):
        raise RuntimeError('Required package manager is missing: '+manager)
    if kind == 'deb':
        fields = output(['dpkg-deb','-f',file,'Package','Version','Architecture','Description'])
        name = output(['dpkg-deb','-f',file,'Package'])
        version = output(['dpkg-deb','-f',file,'Version'])
        arch = output(['dpkg-deb','-f',file,'Architecture'])
        host = output(['dpkg','--print-architecture'])
        try:
            installed = output(['dpkg-query','-W','-f=${Version}',name])
        except subprocess.CalledProcessError:
            installed = ''
        if installed and subprocess.run(['dpkg','--compare-versions',version,'lt',installed]).returncode == 0:
            raise RuntimeError('Downgrades are not supported.')
    else:
        fields = output(['rpm','-qp','--queryformat','%{NAME}\n%{VERSION}-%{RELEASE}\n%{ARCH}\n%{SUMMARY}\n',file])
        name, version, arch = fields.splitlines()[:3]
        host = output(['rpm','--eval','%{_arch}'])
        try:
            installed = output(['rpm','-q','--queryformat','%{VERSION}-%{RELEASE}',name])
        except subprocess.CalledProcessError:
            installed = ''
        if arch in ('src','nosrc'):
            raise RuntimeError('Source RPMs are not supported.')
        # Let the manager handle RPM version ordering; upgrades only below.
    if arch not in (host,'all','noarch'):
        raise RuntimeError('Package architecture does not match this computer.')
    return dict(file=file,kind=kind,manager=manager,name=name,version=version,description=fields,installed=installed)


def install(info):
    if info['installed'] == info['version']:
        print(info['name']+' is already installed.')
        return
    manager = shutil.which(info['manager'])
    if info['manager'] == 'apt-get':
        args = [manager,'install','--assume-yes','--no-remove',info['file']]
    elif info['manager'] == 'dnf':
        args = [manager,'--assumeyes','upgrade' if info['installed'] else 'install',info['file']]
    else:
        args = [manager,'--non-interactive','install','--no-allow-downgrade',info['file']]
    subprocess.run(['pkexec',*args], stdin=subprocess.DEVNULL, check=True)
    print('Installation complete. Find the application in your application menu.')

if __name__ == '__main__':
    try:
        info = inspect(sys.argv[2])
        if sys.argv[1] == '--inspect':
            print(json.dumps(info))
        else:
            install(info)
    except Exception as error:
        print(str(error),file=sys.stderr)
        sys.exit(1)
