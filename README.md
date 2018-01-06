# Tome

Phabricator is an excellent project-management solution.  

However, arcanist is a fairly large pain in the rear to install for Windows users.

Tome is a wrapper around arcanist that also features a semi-automated installer for arcanist and its dependencies on Windows.

# Compiling

1. Install Python 3.6 with pip
2. `pip install -r requirements.txt`
3. Run `build-win.cmd` to compile.  Install UPX for a smaller installer and more false positives from antivirus.
