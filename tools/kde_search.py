#!/usr/bin/env python3
"""Search KDE's actual launcher during explicitly authorized desktop tests."""
import sys,time
from desktop_probe import walk,Atspi
subject=sys.argv[1]
def shellnodes():
 root=Atspi.get_desktop(0)
 for i in range(root.get_child_count()):
  app=root.get_child_at_index(i)
  if app.get_name()=='plasmashell':return list(walk(app))
 return []
for node in shellnodes():
 if node.get_name()=='Application Launcher' and node.get_role_name()=='button':
  actions=node.get_action_iface();actions.do_action(0);break
for _ in range(30):
 for node in shellnodes():
  if node.get_name()=='Search' and node.get_role_name()=='text' and node.get_state_set().contains(Atspi.StateType.SHOWING):
   edit=node.get_editable_text_iface()
   if edit:edit.set_text_contents(subject);break
 else:time.sleep(.2);continue
 break
time.sleep(1)
items=[n for n in shellnodes() if n.get_name()==subject and n.get_role_name()=='list item']
print('Search results:',len(items),flush=True)
if '--open' in sys.argv:
 if not items:raise SystemExit('No application found in KDE search')
 print('Launch:',items[0].get_action_iface().do_action(0),flush=True)
