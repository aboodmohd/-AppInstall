#!/usr/bin/env python3
"""Explicit desktop integration fixtures; never alters production application records."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import launch_monitor as m

root=m.state_root()/'monitor-integration'
root.mkdir(exist_ok=True)
record=root/'fixtures.json'
apps=m.data_root().parent/'applications'
if len(sys.argv)>1 and sys.argv[1]=='--cleanup':
    saved=json.loads(record.read_text())
    for key in saved['keys']:
        spec=m.registry().get(key)
        last=m.latest(key) or {}
        if last.get('notification_id'):
            subprocess.run(['gdbus','call','--session','--dest','org.freedesktop.Notifications','--object-path','/org/freedesktop/Notifications','--method','org.freedesktop.Notifications.CloseNotification',str(last['notification_id'])],capture_output=True)
        if spec:
            path=Path(spec['desktop'])
            if path.name.startswith('appinstall-fixture-'):
                path.unlink(missing_ok=True);m.update_registry(key,None)
    pid=saved['server_pid']
    try:
        cmdline=Path('/proc')/str(pid)/'cmdline'
        if str(root/'port.json').encode() in cmdline.read_bytes():os.kill(pid,signal.SIGTERM)
    except (FileNotFoundError,ProcessLookupError):pass
    print('Removed only AppInstall test launchers and its owned port-holder process.')
    raise SystemExit
server="import json,socket,sys,time;server=socket.socket();server.bind(('127.0.0.1',0));server.listen();open(sys.argv[1],'w').write(json.dumps({'port':server.getsockname()[1]}));time.sleep(600)"
process=subprocess.Popen([sys.executable,'-c',server,str(root/'port.json')],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
for _ in range(30):
    if (root/'port.json').exists():break
    time.sleep(.1)
port=json.loads((root/'port.json').read_text())['port']
fixtures={
 'missing-library':('AppInstall Library Test',m.desktop_quote(root/'missing-library-test'),{}),
 'port':('AppInstall Port Test',m.desktop_quote(sys.executable)+' -c '+m.desktop_quote("import socket,sys;s=socket.socket();\ntry:s.bind(('127.0.0.1',"+str(port)+"))\nexcept OSError:print('Error: port "+str(port)+" is already in use',flush=True);sys.exit(1)"),{}),
 'executable':('AppInstall Executable Test','/appinstall-fixture-missing-executable',{}),
 'container':('AppInstall Container Test','distrobox-enter -n appinstall-fixture-missing-container -- true',{'container':'appinstall-fixture-missing-container'}),
 'crash':('AppInstall Crash Test',m.desktop_quote(sys.executable)+' -c '+m.desktop_quote("import sys;print('Intentional startup failure',flush=True);sys.exit(70)"),{}),
 'background':('AppInstall Background Test',m.desktop_quote(sys.executable)+' -c '+m.desktop_quote("import subprocess,sys;subprocess.Popen([sys.executable,'-c','import time;time.sleep(3)']);sys.exit(0)"),{}),
}
keys=[]
for suffix,(name,command,extra) in fixtures.items():
    path=apps/('appinstall-fixture-'+suffix+'.desktop')
    if path.exists():raise RuntimeError('Fixture launcher already exists; refusing to overwrite it.')
    path.write_text('[Desktop Entry]\nType=Application\nName='+name+'\nIcon=dialog-information\nCategories=Utility;\nTerminal=false\nExec='+command+'\n')
    key='test:'+suffix;m.wrap_desktop(key,path,'test',**extra);keys.append(key)
m.atomic_json(record,dict(keys=keys,server_pid=process.pid,port=port))
print('Created controlled test fixtures; port holder:',process.pid,'port:',port)
