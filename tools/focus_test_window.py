#!/usr/bin/env python3
"""Temporarily focus a named test window using KWin; does not change settings."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
caption=sys.argv[1]
script='for (const w of workspace.windowList()) { if (w.caption === '+json.dumps(caption)+') { w.minimized=false;workspace.activeWindow=w;break; } }'
with tempfile.TemporaryDirectory(prefix='appinstall-focus-') as directory:
 path=Path(directory)/'focus.js';path.write_text(script)
 plugin='appinstall-monitor-test-focus'
 identifier=subprocess.check_output(['qdbus6','org.kde.KWin','/Scripting','org.kde.kwin.Scripting.loadScript',str(path),plugin],text=True).strip()
 try:
  subprocess.run(['qdbus6','org.kde.KWin','/Scripting/Script'+identifier,'org.kde.kwin.Script.run'],check=True)
  time.sleep(.4)
  if len(sys.argv)>2:subprocess.run(['spectacle','-a','-b','-n','-o',sys.argv[2]],check=True)
 finally:subprocess.run(['qdbus6','org.kde.KWin','/Scripting','org.kde.kwin.Scripting.unloadScript',plugin],check=True,stdout=subprocess.DEVNULL)
