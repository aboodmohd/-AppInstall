#!/usr/bin/env python3
"""Explicit controlled KDE launch tests; requires fixtures and desktop accessibility."""
import json
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import launch_monitor as m
here=Path(__file__).resolve().parent
results=[]
for suffix,name,expected in [('executable','AppInstall Executable Test','executable'),('container','AppInstall Container Test','container'),('crash','AppInstall Crash Test','crash'),('background','AppInstall Background Test',None)]:
    key='test:'+suffix;before=m.latest(key)
    subprocess.run([sys.executable,str(here/'kde_search.py'),name,'--open'],check=True)
    attempt=None
    for _ in range(120):
        current=m.latest(key)
        if current and (not before or current['id']!=before['id']) and current['status'] not in ('checking','starting'):
            attempt=current;break
        time.sleep(.25)
    if not attempt:raise RuntimeError('No monitored result for '+name)
    category=(attempt.get('error') or {}).get('category')
    print(name,'status',attempt['status'],'category',category,flush=True)
    assert category==expected,(category,expected)
    time.sleep(.7)
    if expected:
        subprocess.run(['spectacle','-b','-n','-o',str(m.state_root()/'monitor-integration'/('kde-'+suffix+'.png'))],check=True)
        subprocess.run([sys.executable,str(here/'monitor_ui_drive.py'),name,'Close'],check=True)
    attempt=m.latest(key)
    if attempt.get('notification_id'):
        subprocess.run(['gdbus','call','--session','--dest','org.freedesktop.Notifications','--object-path','/org/freedesktop/Notifications','--method','org.freedesktop.Notifications.CloseNotification',str(attempt['notification_id'])],capture_output=True)
    results.append(dict(key=key,status=attempt['status'],category=category,kde_launch=True))
m.atomic_json(m.state_root()/'monitor-integration/desktop-results.json',results)
print('Controlled KDE launch tests passed.',flush=True)
