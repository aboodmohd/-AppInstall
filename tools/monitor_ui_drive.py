#!/usr/bin/env python3
"""Invoke only a specifically named AppInstall test dialog control through AT-SPI."""
import sys,time
from desktop_probe import walk,Atspi
subject,button=sys.argv[1:3]
for _ in range(40):
 root=Atspi.get_desktop(0)
 for i in range(root.get_child_count()):
  app=root.get_child_at_index(i)
  if app.get_name()!='diagnostics_ui.py':continue
  for j in range(app.get_child_count()):
   dialog=app.get_child_at_index(j)
   if dialog is None:continue
   nodes=list(walk(dialog))
   if not any(subject.lower() in n.get_name().lower() for n in nodes):continue
   for n in nodes:
    if n.get_name()!=button or n.get_role_name()!='button':continue
    action=n.get_action_iface()
    if action:
     for index in range(action.get_n_actions()):
      if action.get_action_name(index)=='Press':
       print('Invoked',button,action.do_action(index));raise SystemExit
 time.sleep(.2)
raise SystemExit('The requested dialog/button was not available.')
