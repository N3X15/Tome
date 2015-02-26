'''
This is intended to be compiled with pyinstaller.
'''

TOME_VERSION='0.1.1'

import os, sys, argparse, subprocess

script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(script_dir, 'lib', 'buildtools'))

from buildtools import cmd, log, http
from buildtools import os_utils
from buildtools.wrapper import Git
from buildtools.bt_logging import IndentLogger

home_dir = os.path.expanduser('~')

arcinstall_dir = os.path.join(home_dir, '.arcanist')
libphutil_dir = os.path.join(arcinstall_dir, 'libphutil')
arcanist_dir = os.path.join(arcinstall_dir, 'arcanist')
arcanist_bin_dir = os.path.join(arcanist_dir, 'bin')
tome_cfg = os.path.join(arcinstall_dir,'config.json')

libphutil_uri = 'git://github.com/facebook/libphutil.git'
arcanist_uri = 'git://github.com/facebook/arcanist.git'

php_version = '5.6.6'
winphp_uri = 'http://windows.php.net/downloads/releases/php-5.6.6-Win32-VC11-x86.zip'
winphp_sha1 = '0e93bfee3e843cd9fbd4719576f7fe27b3a428dc'
winphp_extract = os.path.join(arcinstall_dir, 'php')
php_bin = 'php'

DISTRO = None
ENV_TYPE = None

packagedefs = {
    'ubuntu':{
        'git': ['git-core'],
        'php': ['php5-cli', 'php5-curl']
    },
    'debian':{
        'git': ['git-core'],
        'php': ['php5-cli', 'php5-curl']
    }
}

def CloneOrPull(id, uri, dir):
    if not os.path.isdir(dir):
        cmd(['git', 'clone', uri, dir], echo=True, show_output=True, critical=True)
    else:
        with os_utils.Chdir(dir):
            cmd(['git', 'pull'], echo=True, show_output=True, critical=True)
    with os_utils.Chdir(dir):            
        log.info('{} is now at commit {}.'.format(id, Git.GetCommit()))
        
def CheckInstall():
    packages = []
    path = []
    with log.info('Checking for Git...'):
        if not os_utils.which('git'):
            if sys.platform == 'win32':
                log.error('Git for Windows is missing from PATH.  Please install it.')
                sys.exit(1)
            else:
                packages += package_defs[DISTRO]['git']
        else:
            log.info('Git is present in PATH.')
            
    with log.info('Checking for PHP...'):
        if not os_utils.which('php'):
            if sys.platform == 'win32':
                WindowsInstallPHP()
                path += [winphp_extract]
            else:
                packages += package_defs[DISTRO]['php']
        else:
            log.info('PHP is present in PATH.')
                
    if len(packages) > 0:
        os_utils.InstallDpkgPackages(packages)
        
    with log.info('Checking arcanist installation...'):
        if not os.path.isdir(arcinstall_dir):
            log.info('mkdir ' + arcinstall_dir)
        
        CloneOrPull('libphutil', libphutil_uri, libphutil_dir)
        need_arcanist_path = not os.path.isdir(arcanist_dir)
        CloneOrPull('arcanist', arcanist_uri, arcanist_dir)
        
        if not os_utils.which('php'):
            path += [arcanist_bin_dir]
        else:
            log.info('Arcanist is present in PATH.')
        
    if len(path) == 0:
        return
    if sys.platform == 'win32':
        with log.info('Connecting to Windows to adjust {} PATH...'.format(ENV_TYPE)):
            env = WindowsEnv(ENV_TYPE)
            oldPath = env.get('PATH', '').split(os.pathsep)
            newPath = path
            for pathSeg in oldPath:
                if pathSeg in newPath:
                    log.warning('Path segment "{}" has a duplicate.  Skipping.'.format(pathSeg))
                    continue
                if not os.path.isdir(pathSeg):
                    log.warning('Path segment "{}" does not exist!  Recommend removal.'.format(pathSeg))
                    # continue
                newPath += [pathSeg.strip()]
                    
            fixed_pathstr = os.pathsep.join(newPath)
            log.info('Updating {} %PATH% to: {}'.format(ENV_TYPE, fixed_pathstr))
            env.set('PATH',fixed_pathstr)
    else:
        with open(os.path.expanduser('~/.bashrc'), 'a') as f:
            for pathc in path:
                with log.info('Adding {} to PATH (via ~/.bashrc)...'.format(pathc)):
                    f.write('\nexport PATH="{0}:$PATH"'.format(pathc))
        
def WindowsInstallPHP():
    import zipfile, hashlib
    phpzip = 'php-{}.zip'.format(php_version)
    if not os.path.isfile(phpzip):
        with log.info('Downloading PHP...'):
            http.DownloadFile(winphp_uri, phpzip)
    with log.info('Verifying PHP ZIP against known SHA1...'):
        real_sha1 = ''
        with open(phpzip, 'rb') as f:
            real_sha1 = hashlib.sha1(f.read()).hexdigest()
        if real_sha1 != winphp_sha1:
            log.error('SHA1 mismatch! {} != {}'.format(real_sha1, winphp_sha1))
            sys.exit(1)
        else:
            log.info('Hashes match.')
    with log.info('Installing PHP...'):
        log.info('Extracting ZIP...')
        with zipfile.ZipFile(phpzip, "r") as z:
            z.extractall(winphp_extract)
        with log.info('Updating php.ini configuration...'):
            phpini = os.path.join(winphp_extract, 'php.ini')
            with open(phpini + '-development', 'r') as infile:
                with open(phpini, 'w') as outfile:
                    for line in infile:
                        line = line.strip()
                        if 'extension_dir = "ext"' in line:
                            line = 'extension_dir = "{}"'.format(os.path.join(winphp_extract, 'ext'))
                            outfile.write(line + '\n')
                            log.info('Set ' + line)
                            
                        orig_comment = comment = line.startswith(';') 
                        if comment:
                            line = line[1:]
                            
                            if 'php_curl.dll' in line:
                                comment = False
                                
                        
                        if orig_comment and not comment:
                            log.info('Uncommented ' + line)
                        elif not orig_comment and comment:
                            log.info('Commented ' + line)
                        if comment:
                            line = ';' + line
                        outfile.write(line + '\n')
        log.info('Finished writing {}'.format(phpini))
    
            
if __name__ == '__main__':
    argp = argparse.ArgumentParser(prog='tome', description='Installer for Arcanist.', version=TOME_VERSION)
    command = argp.add_subparsers(help='The command you wish to execute', dest='MODE')
    
    _install = command.add_parser('install', help='Install or update Arcanist.')
    _install.add_argument('--arcbase-dir', type=str, default=arcinstall_dir, help='Directory to install Arcanist, PHP, and phutil.')
    _install.add_argument('--user', action='store_true', default=False, help='Modify Windows user %PATH% (rather than system).')
    
    _setup = command.add_parser('setup-project', help='Set up working directory for phabricator')
    _setup.add_argument('phab_uri', type=str, help='URL of Phabricator')
    
    # _diff = command.add_parser('diff', help='Run arc diff')
    
    args = argp.parse_args()
    
    if sys.platform == 'linux':
        DISTRO, _, _ = platform.linux_distribution()
        DISTRO = DISTRO.lower()
        log.info('Distro is '+DISTRO)
        
    
    if sys.platform == 'win32':
        ENV_TYPE='user' 
        if not args.user:
            from win32com.shell import shell
            if not shell.IsUserAnAdmin():
                log.error('Please run tome as administrator to modify system %PATH%.  If you only wish to modify your user\'s %PATH%, please add --user to the command line.')
                sys.exit(1)
            ENV_TYPE='system'
        
    if args.MODE == 'install':
        if args.arcbase_dir is not None:
            arcinstall_dir = os.path.realpath(args.arcbase_dir)
        log.info('Installing to '+arcinstall_dir)
        if ENV_TYPE is not None:
            log.info('Will modify {} environment variables.'.format(ENV_TYPE))
        CheckInstall()
        
    if args.MODE == 'setup-project':
        import json
        arc_config = {}
        arc_config['phabricator.uri'] = args.phab_uri
        with open('.arcconfig', 'w') as f:
            json.dump(arc_config, f, sort_keys=True, indent=4, separators=(',', ': '))
        log.info('Created .arcconfig.')
