# -*- mode: python -*-
import sys
a = Analysis(['tome.py'],
             hookspath=None)
#files = os.listdir('icons')
#for file in files:
#    a.datas += [('icons' + os.sep + file, 'icons' + os.sep + file, 'DATA')]

pyz = PYZ(a.pure)

ename=os.path.join('bin', 'tome')
if sys.platform.startswith('win') or sys.platform.startswith('microsoft'):
    ename += '.exe'

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name=ename,
          debug=False,
          strip=None,
          upx=True,
          console=True,
          #icon=os.path.join('icons','squad-bw.ico')
)
#app = BUNDLE(exe, name='Tome.app')
