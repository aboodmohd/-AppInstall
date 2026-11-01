#!/usr/bin/env python3
"""Manual integration helper: inspect or invoke a named accessible UI control."""
import gi
import sys
gi.require_version('Atspi','2.0')
from gi.repository import Atspi

def walk(node,depth=0):
    if node is None or depth>22: return
    yield node
    if node.get_role_name() in ('menu bar','popup menu'): return
    for index in range(min(node.get_child_count(),200)):
        try: yield from walk(node.get_child_at_index(index),depth+1)
        except Exception: continue

def main():
    root=Atspi.get_desktop(0)
    appfilter=sys.argv[1] if len(sys.argv)>1 else ''
    needle=sys.argv[2] if len(sys.argv)>2 else ''
    for index in range(root.get_child_count()):
        app=root.get_child_at_index(index)
        if appfilter and appfilter.lower() not in app.get_name().lower(): continue
        for node in walk(app):
            name=node.get_name()
            if needle.lower() not in name.lower(): continue
            actions=node.get_action_iface()
            actionnames=[actions.get_action_name(i) for i in range(actions.get_n_actions())] if actions else []
            print(repr(name),node.get_role_name(),actionnames,flush=True)
            if len(sys.argv)>3 and name==needle and actions and (len(sys.argv)<5 or node.get_role_name()==sys.argv[4]):
                action=sys.argv[3]
                for i,actionname in enumerate(actionnames):
                    if actionname==action:
                        print('Invoked',actionname,actions.do_action(i),flush=True);sys.exit(0)

if __name__=='__main__':
    main()
