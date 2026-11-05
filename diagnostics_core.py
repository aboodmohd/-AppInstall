"""Diagnostics inventory and explicitly approved repair actions for AppInstall."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import launch_monitor as monitor

# Evidence-based mappings, not arbitrary package names derived from error output.
KNOWN_LIBRARIES={'libasound.so.2':{'deb':'libasound2t64','rpm':'alsa-lib'}}


def applications():
    result=[]
    for key,spec in monitor.registry().items():
        attempts=monitor.history(key)
        last_error=next((item for item in attempts if item.get('error')),None)
        result.append(dict(spec,last=attempts[0] if attempts else None,history=attempts,last_error=last_error))
    return sorted(result,key=lambda item:item['name'].casefold())



def diagnostic_details(record):
    """Separate the latest launch result from the most recent recorded failure."""
    latest = record.get('last') or {}
    previous_failure = record.get('last_error') or {}
    latest_error = latest.get('error') or {}
    failure_error = previous_failure.get('error') or {}

    if latest:
        latest_message = latest_error.get('detail') or (
            'No error detected; the application may still be unusable.'
        )
    else:
        latest_message = 'No launch recorded.'

    if failure_error:
        failure_message = (
            failure_error.get('category', 'unknown') + ' — ' +
            failure_error.get('detail', 'Details unavailable') +
            ' (at ' + previous_failure.get('started', 'unknown time') + ')'
        )
    else:
        failure_message = 'None recorded.'

    return '\n'.join([
        record.get('name', 'Application'),
        'Managed launcher: ' + record.get('desktop', 'Unknown'),
        'Latest attempt: ' + latest.get('started', 'Never'),
        'Latest attempt status: ' + latest.get('status', 'Never launched'),
        'Latest attempt error: ' + latest_message,
        'Most recent recorded failure: ' + failure_message,
        'Latest attempt log: ' + latest.get('log', 'No launch logs yet.'),
    ])


def open_application(key,files=()):
    return subprocess.Popen([sys.executable,str(Path(monitor.__file__).resolve()),'--launch',key,'--',*files],start_new_session=True)


def repair_launcher(key):
    spec=monitor.registry()[key]
    engine=None
    try:
        if spec['format'] in ('deb','rpm'):
            from container_backend import Engine
            engine=Engine()
        monitor.rewrite_launcher(spec)
        if engine and key in engine.registry:
            for entry in engine.registry[key].get('exports',[]):
                if entry['path']==spec['desktop']:entry['sha256']=monitor.registry()[key]['desktop_hash']
            engine.save()
    finally:
        if engine:engine.close()
    return 'The managed launcher was recreated.'


def reexport(key):
    from container_backend import Engine
    engine=Engine()
    try:
        info=engine.registry[key]
        start_container(key)
        if not info.get('desktop'):raise RuntimeError('No primary desktop entry is recorded.')
        info['exports']=engine.export(info,info['desktop']);info['status']='installed';engine.save()
        return 'The container application was re-exported.'
    finally:engine.close()


def start_container(key):
    spec=monitor.registry()[key]
    if not spec.get('container'):raise RuntimeError('This application does not use a container.')
    monitor.checked(['podman','container','exists',spec['container']],15)
    monitor.checked(['distrobox','enter','--name',spec['container'],'--no-tty','--','true'],120)
    return 'Container startup completed. Retry the application.'


def library_packages(key):
    spec=monitor.registry()[key];last=monitor.latest(key) or {}
    libraries=(last.get('error') or {}).get('libraries',[])
    return sorted({KNOWN_LIBRARIES[lib][spec['format']] for lib in libraries if lib in KNOWN_LIBRARIES and spec['format'] in KNOWN_LIBRARIES[lib]})


def dependency_plan(key):
    spec=monitor.registry()[key];packages=library_packages(key)
    if not packages:raise RuntimeError('There is no known safe package mapping for this failure.')
    from container_backend import Engine
    engine=Engine()
    try:
        info=engine.registry[key];start_container(key);engine.ensure(info)
        if spec['format']=='deb':
            text=engine.enter(info,['sudo','apt-get','--simulate','--no-remove','install',*packages]).decode()
        else:
            args=['distrobox','enter','--name',spec['container'],'--no-tty','--','sudo','dnf','--assumeno','install',*packages]
            completed=subprocess.run(args,env=dict(os.environ,DBX_CONTAINER_MANAGER='podman',LC_ALL='C'),capture_output=True,text=True)
            text=completed.stdout+completed.stderr
            if completed.returncode and 'Operation aborted' not in text:raise RuntimeError(text)
        return dict(packages=packages,text=monitor.redact(text),format=spec['format'])
    finally:engine.close()


def install_repair(key,plan):
    # Caller must present plan and obtain explicit approval, then use this exact list.
    if plan['packages']!=library_packages(key):raise RuntimeError('The diagnostic evidence changed; review the repair again.')
    from container_backend import Engine
    engine=Engine()
    try:
        info=engine.registry[key];start_container(key);engine.ensure(info)
        if plan['format']=='deb':args=['sudo','apt-get','--assume-yes','--no-remove','install',*plan['packages']]
        else:args=['sudo','dnf','--assumeyes','install',*plan['packages']]
        engine.enter(info,args)
        engine.registry[key].setdefault('diagnostic_repairs',[]).append(dict(packages=plan['packages']))
        engine.save()
        return 'The approved dependencies were installed inside the container. Retry the application.'
    finally:engine.close()


def port_owner(key):
    last=monitor.latest(key) or {};port=(last.get('error') or {}).get('port')
    if not isinstance(port,int) or not 1<=port<=65535:raise RuntimeError('No conflicting port was identified in the launch output.')
    return monitor.redact(monitor.checked(['ss','-ltnp','sport = :'+str(port)],10))


def uninstall(key):
    spec=monitor.registry()[key]
    if spec['format'] in ('deb','rpm'):
        from container_backend import Engine
        engine=Engine()
        try:engine.uninstall(key)
        finally:engine.close()
    elif spec['format']=='flatpak':
        monitor.checked(['flatpak','uninstall','--user','--noninteractive','--assumeyes',spec['appid']],300)
        remove_owned_launcher(spec)
    elif spec['format']=='appimage':
        import shutil
        manifest=Path(spec['manifest']);info=json.loads(manifest.read_text())
        generation=Path(info['generation'])
        if not generation.name.startswith('.appinstall-') or generation.is_symlink():raise RuntimeError('The recorded AppImage directory is not safe to remove.')
        shutil.rmtree(generation);manifest.unlink();remove_owned_launcher(spec)
    else:raise RuntimeError('Uninstall is not supported for this entry.')
    monitor.update_registry(key,None)
    return 'Application removed. Personal application data and diagnostic history were kept.'


def remove_owned_launcher(spec):
    path=Path(spec['desktop'])
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==spec.get('desktop_hash'):
        path.unlink()
