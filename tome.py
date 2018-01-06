'''
This is intended to be compiled with pyinstaller.
'''
import argparse
import os
import platform
import re
import subprocess
import sys
from buildtools import cmd, cmd_output, http, log, os_utils
from buildtools.bt_logging import IndentLogger
from buildtools.wrapper import Git

import requests
from lxml import etree, html
from semantic_version import Version

TOME_VERSION = '0.2.0'

home_dir = os.path.expanduser('~')

arcinstall_dir = os.path.join(home_dir, '.arcanist')
libphutil_dir = os.path.join(arcinstall_dir, 'libphutil')
arcanist_dir = os.path.join(arcinstall_dir, 'arcanist')
arcanist_bin_dir = os.path.join(arcanist_dir, 'bin')
tome_cfg = os.path.join(arcinstall_dir, 'config.json')

libphutil_uri = 'git://github.com/facebook/libphutil.git'
arcanist_uri = 'git://github.com/facebook/arcanist.git'

REG_WINPKG_IDENTIFIER = re.compile(r'php-(\d+).(\d+)-ts-VC15-x64')
# /downloads/releases/php-7.2.1-Win32-VC15-x64.zip
REG_GET_WINPHP_VERSION = re.compile(r'/downloads/releases/php\-(\d+\.\d+\.\d+)\-Win32\-VC15\-x64\.zip')
REG_GET_PHP_VERSION = re.compile(r'/get/php\-(\d+\.\d+\.\d+)\.tar\.gz/from/a/mirror')
WINPHP_BASE = 'http://windows.php.net' # TLS times out. :(
WINPHP_DOWNLOADS = '/download'
PHP_BASE = 'https://php.net'
PHP_DOWNLOADS = '/downloads.php'


def detect_winphp_version():
    tree = html.parse(WINPHP_BASE+WINPHP_DOWNLOADS, etree.HTMLParser())
    for box in tree.xpath('//div[@class="innerbox"]'):
        # Check <h4> contents.
        for li in box.findall('./ul/li'):
            #log.info(li)
            a = li.find('a')
            #log.info(a.text)
            if a.text.strip() != 'Zip':
                continue
            href = a.get('href')
            log.info(href)
            m = REG_GET_WINPHP_VERSION.match(href)
            if m is not None:
                download_uri = WINPHP_BASE + href
                # /downloads/releases/php-7.2.1-nts-Win32-VC15-x64.zip
                sha256 = li.find('./span[@class="md5sum"]').text.split(':')[-1].strip()
                return Version(m.group(1)), download_uri, sha256
    return None


def detect_php_version():
    tree = html.parse(WINPHP_DOWNLOADS, etree.HTMLParser())
    for versionblock in tree.xpath('//div[@class="content-box"]/ul/li'):
        # First <a> is the download link.
        a = versionblock.find('a')
        href = a.get('href')
        m = REG_GET_PHP_VERSION.match(href)
        version = Version(m.group(1))
        download_uri = PHP_BASE + href
        sha256 = versionblock.find('./span[@class="sha256"]').text.strip()
        return version, download_uri, sha256
    return None


winphp_extract = os.path.join(arcinstall_dir, 'php')
php_bin = 'php'

DISTRO = None
ENV_TYPE = None

package_defs = {
    'ubuntu': {
        'git': ['git-core'],
        'php': ['php5-cli', 'php5-curl']
    },
    'debian': {
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


def CheckPHPVersion(release_info):
    stdout, _ = cmd_output(['php', '--version'])
    version = stdout.decode('utf-8').split(' ')[1]
    log.info('PHP version %s detected.', version)
    return release_info[0] == Version(version) or sys.platform != 'win32'  # Ignore version on non-windows platforms. (Package management!)


def CheckInstall(release_info):
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
        if not os_utils.which('php') or not CheckPHPVersion(release_info):
            if sys.platform == 'win32':
                WindowsInstallPHP(release_info)
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
        #need_arcanist_path = not os.path.isdir(arcanist_dir)
        CloneOrPull('arcanist', arcanist_uri, arcanist_dir)

        if not os_utils.which('php'):
            path += [arcanist_bin_dir]
        else:
            log.info('Arcanist is present in PATH.')

    if len(path) == 0:
        return
    if sys.platform == 'win32':
        with log.info('Connecting to Windows to adjust {} PATH...'.format(ENV_TYPE)):
            env = os_utils.WindowsEnv(ENV_TYPE)
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
            env.set('PATH', fixed_pathstr)
    else:
        with open(os.path.expanduser('~/.bashrc'), 'a') as f:
            for pathc in path:
                with log.info('Adding {} to PATH (via ~/.bashrc)...'.format(pathc)):
                    f.write('\nexport PATH="{0}:$PATH"'.format(pathc))


def WindowsInstallPHP(release_info):
    import zipfile
    import hashlib
    release_version, release_url, release_sha256 = release_info
    phpzip = 'php-{}.zip'.format(release_version)
    if not os.path.isfile(phpzip):
        with log.info('Downloading PHP...'):
            http.DownloadFile(release_url, phpzip)
    with log.info('Verifying PHP ZIP against known SHA1...'):
        real_sha256 = ''
        if os.path.isfile(phpzip):
            with open(phpzip, 'rb') as f:
                real_sha256 = hashlib.sha256(f.read()).hexdigest()
        if real_sha256 != release_sha256:
            log.error('SHA256 mismatch! {} != {}'.format(real_sha256, release_sha256))
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
                            if 'php_openssl.dll' in line:
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
    argp = argparse.ArgumentParser(prog='tome', description='Installer for Arcanist.')
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
        log.info('Distro is ' + DISTRO)

    if args.MODE == 'install':
        release_info = (None, None, None)
        if sys.platform == 'win32':
            release_info = detect_winphp_version()
            ENV_TYPE = 'user'
            if not args.user:
                from win32com.shell import shell
                if not shell.IsUserAnAdmin():
                    log.error('Please run tome as administrator to modify system %PATH%.  If you only wish to modify your user\'s %PATH%, please add --user to the command line.')
                    sys.exit(1)
                ENV_TYPE = 'system'
        else:
            release_info = detect_php_version()

        with log.info('Latest version of PHP for this platform:'):
            log.info('Version.: %s', release_info[0])
            log.info('URL.....: %s', release_info[1])
            log.info('SHA256..: %s', release_info[2])
            
        if args.arcbase_dir is not None:
            arcinstall_dir = os.path.realpath(args.arcbase_dir)
        log.info('Installing to ' + arcinstall_dir)
        if ENV_TYPE is not None:
            log.info('Will modify {} environment variables.'.format(ENV_TYPE))
        CheckInstall(release_info)

    elif args.MODE == 'setup-project':
        import json
        arc_config = {}
        arc_config['phabricator.uri'] = args.phab_uri
        with open('.arcconfig', 'w') as f:
            json.dump(arc_config, f, sort_keys=True, indent=4, separators=(',', ': '))
        log.info('Created .arcconfig.')
    else:
        argp.print_usage()
