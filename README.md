# Tome

Phabricator is an excellent project-management solution.  

However, arcanist is a fairly large pain in the rear to install for Windows users.

Tome is a wrapper around arcanist that also features a semi-automated installer for arcanist and its dependencies on Windows.

# Compiling

Tome requires Python 2.7 and pyinstaller (which itself requires pywin32).

After those two dependencies are installed, simply run ```build-win.cmd``` to create tome.exe in the dist directory.
