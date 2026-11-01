#!/usr/bin/env python3
"""Explicitly run only approved AppInstall integration-test UI actions."""
import json
from pathlib import Path
import sys
import time
from desktop_probe import walk,Atspi
subject=sys.argv[1]
sequence=sys.argv[2:]
deadline=time.monotonic()+300
while sequence and time.monotonic()<deadline:
    root=Atspi.get_desktop(0)
    for i in range(root.get_child_count()):
        app=root.get_child_at_index(i)
        if app.get_name()!='container_ui.py':continue
        nodes=list(walk(app))
        if not any(subject.lower() in n.get_name().lower() for n in nodes):continue
        for node in nodes:
            if node.get_name()!=sequence[0] or node.get_role_name()!='button':continue
            action=node.get_action_iface()
            if not action:continue
            for index in range(action.get_n_actions()):
                if action.get_action_name(index)=='Press':
                    print('Click',sequence[0],flush=True)
                    action.do_action(index);sequence.pop(0)
                    break
            else:continue
            break
        break
    time.sleep(.4)
if sequence:raise SystemExit('Timed out waiting for '+repr(sequence))
print('UI sequence complete',flush=True)
