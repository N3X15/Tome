'''
This is intended to be compiled with pyinstaller.
'''
import os, sys, argparse

script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(script_dir, 'lib', 'buildtools'))

from buildtools import cmd, log, http
from buildtools import os_utils
from buildtools.wrapper import Git
from buildtools.bt_logging import IndentLogger

arcinstall_dir = os.path.realpath(os.path.expanduser('~/.arcanist'))
libphutil_dir = os.path.join(arcinstall_dir, 'libphutil')
arcanist_dir = os.path.join(arcinstall_dir, 'arcanist')
arcanist_bin_dir = os.path.join(arcanist_dir, 'bin')

libphutil_uri = 'git://github.com/facebook/libphutil.git'
arcanist_uri = 'git://github.com/facebook/arcanist.git'

winphp_uri = 'http://windows.php.net/downloads/releases/php-5.6.4-Win32-VC11-x86.zip'
winphp_sha1 = '3c72be4d02990a15e55a648acc9f89540cadeba6'
winphp_extract = os.path.realpath('C:\\php')
php_bin = 'php'

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
                packages += package_defs['ubuntu']['git']
        else:
            log.info('Git is present.')
            
    with log.info('Checking for PHP...'):
        if not os_utils.which('php'):
            if sys.platform == 'win32':
                WindowsInstallPHP()
                path += [winphp_extract]
            else:
                packages += package_defs['ubuntu']['php']
        else:
            log.info('PHP is present.')
                
    if len(packages) > 0:
        os_utils.InstallDpkgPackages(packages)
        
    with log.info('Checking arcanist installation...'):
        if not os.path.isdir(arcinstall_dir):
            log.info('mkdir ' + arcinstall_dir)
        
        CloneOrPull('libphutil', libphutil_uri, libphutil_dir)
        need_arcanist_path = not os.path.isdir(arcanist_dir)
        CloneOrPull('arcanist', arcanist_uri, arcanist_dir)
        path += [arcanist_bin_dir]
        
    if sys.platform == 'win32':
        log.info('Please add this to your Windows user\'s PATH: ' + (';'.join(path)))
    else:
        if len(path) > 0:
            with open(os.path.expanduser('~/.bashrc'), 'a') as f:
                for pathc in path:
                    with log.info('Adding {} to PATH (via ~/.bashrc)...'.format(pathc)):
                        f.write('\nexport PATH="{0}:$PATH"'.format(pathc))
        
def WindowsInstallPHP():
    import zipfile, hashlib
    if not os.path.isfile('php.zip'):
        with log.info('Downloading PHP...'):
            http.DownloadFile(winphp_uri, 'php.zip')
    with log.info('Verifying PHP ZIP against known SHA1...'):
        real_sha1 = ''
        with open('php.zip', 'rb') as f:
            real_sha1 = hashlib.sha1(f.read()).hexdigest()
        if real_sha1 != winphp_sha1:
            log.error('SHA1 mismatch! {} != {}'.format(real_sha1, winphp_sha1))
            sys.exit(1)
        else:
            log.info('Hashes match.')
    with log.info('Installing PHP...'):
        log.info('Extracting ZIP...')
        with zipfile.ZipFile('php.zip', "r") as z:
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
    argp = argparse.ArgumentParser()
    command = argp.add_subparsers(help='The command you wish to execute', dest='MODE')
    
    _install = command.add_parser('install', help='Install or update arcanist.')
    
    _setup = command.add_parser('setup-project', help='Set up working directory for phabricator')
    _setup.add_argument('phab_uri', type=str, help='URL of Phabricator')
    
    # _diff = command.add_parser('diff', help='Run arc diff')
    
    args = argp.parse_args()
    
    if args.MODE == 'install':
        CheckInstall()
    if args.MODE == 'setup-project':
        import json
        arc_config = {}
        arc_config['phabricator.uri'] = args.phab_uri
        with open('.arcconfig', 'w') as f:
            json.dump(arc_config, f, sort_keys=True, indent=4, separators=(',', ': '))
        log.info('Created .arcconfig.')
