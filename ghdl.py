#!/usr/bin/python

import urllib.request
import base64
import json
import sys
import re
import os
import glob
import tempfile
import tarfile
import shutil
import argparse

from zipfile import ZipFile

def get_api_data(org, project):
    """Get latest version of a project on GitHub"""

    url = "https://api.github.com/repos/{}/{}/releases/latest".format(org, project)
    print("URL: ", url)

    credentials = ('%s:%s' % (username, token))
    encoded_credentials = base64.b64encode(credentials.encode('ascii'))

    try:
        req = urllib.request.Request(url)
        req.add_header('Authorization', 'Basic %s' % encoded_credentials.decode('ascii'))
        response = urllib.request.urlopen(req)
    except:
        print('Cannot open ', download_url)
        sys.exit(1)

    response_data = response.read()
    json_data = json.loads(response_data)

    return json_data


def get_latest_list(data):
    """Get list of download URLs from blob of API data"""

    links = []
    for asset in data['assets']:
        links.append(asset['browser_download_url'])

    return links


def filter_urls(urls, myArch, myOS):
    """
    Filters list of URLs to only those for the right OS and architecture
    """
    new_urls = []

    for url in urls:
        if myOS in url.lower():
            new_urls.append(url)

    if myArch == "x86_64":
        arch_r = re.compile('.*64bit.*|.*x86_64.*|.*amd64.*')
    elif myArch == "aarch64":
        arch_r = re.compile('.*aarch64.*|.*arm64.*|.*arm8.*|.*armv8.*')
    elif myArch == "armv7":
        # Assumption is that plain 'arm' refers to armv7
        arch_r = re.compile('.*armv7.*|.*arm7.*|.*arm')
    elif myArch == "i386":
        arch_r = re.compile('.*386.*')

    urls = [ x for x in new_urls if arch_r.match(x, re.IGNORECASE) ]

    if len(urls) == 0 and len(new_urls) > 0:
        return new_urls
    else:
        return urls


def filter_extensions(urls, myOS):
    """
    Filters list of URLs to only those files with the right extension
    Prefers tarballs for Linux and MacOS, zipfiles for Windows
    If list ends up empty, returns the original list.
    """

    # Filter useless extensions, like for checksums, text files, debs, rpms, etc.
    ext_r = re.compile('.*asc|.*sha512.*|.*md5.*|.*sha1.*|.*sha2*|.*txt|.*deb|.*rpm')
    urls = [ x for x in urls if not ext_r.match(x, re.IGNORECASE) ]

    if myOS == "linux" or myOS == "darwin":
        ext_r = re.compile('.*tar.gz|.*tar.xz|.*tar.bz|.*tar.bz2')
    elif myOS == "windows":
        ext_r = re.compile('.*zip')

    new_urls = [ x for x in urls if ext_r.match(x, re.IGNORECASE) ]

    if len(new_urls) == 0 and len(urls) > 0:
        return urls
    else:
        return new_urls


def get_latest_version(data):
    """Get the version of the latest release, based on list of URLs"""

    return data['tag_name']


def get_binary(urls, bindir, linkdir):
    """
    Download the latest version of the binary and handle it
    """

    if len(urls) == 1:
        url = urls[0]
    else:
        print("WARNING: More than one candidate binary found.")
        print("Using first found binary. This might yield unexpected results.")
        url = urls[0]

    # we use a tmpdir so we can easily remove the whole download later
    tmpdir = tempfile.mkdtemp()
    name = os.path.basename(url)
    targetfile = tmpdir + '/' + name
    urllib.request.urlretrieve(url, targetfile)
    print("Downloaded file: " + tmpdir + '/' + name)
    os.chdir(tmpdir)
    
    extracted = False
    if 'tar' in name:
        mytar = tarfile.open(targetfile)
        mytar.extractall()                                                                 
        os.remove(targetfile)                                                                  
        extracted = True
    elif 'zip' in name:
        with ZipFile(targetfile, 'r') as myzip:                                            
            myzip.extractall()                                                             
        os.remove(targetfile)                                                                  
        extracted = True
    else:
        print('name was {}, no tar or zip?'.format(name))

    if extracted:
        # Find largest file in extracted directory
        largest = sorted((os.path.getsize(s), s)                                               
            for s in glob.glob(tmpdir + '/**', recursive=True))[-1][1]                       
        print('Largest file: {}'.format(largest))

        finalfile = os.path.basename(largest).replace('_', '-').split('-')[0]                  
        finalpath = bindir + '/' + finalfile + '-' + latest_version
        shutil.move(largest, finalpath)
    else:
        finalfile = os.path.basename(targetfile).replace('_', '-').split('-')[0]                  
        finalpath = bindir + '/' + finalfile + '-' + latest_version
        shutil.move(targetfile, finalpath)
     
    finallink = linkdir + '/' + finalfile
    os.chmod(finalpath, 0o755)                                                             
    print("Cleaning up temporary directory")
    shutil.rmtree(tmpdir)                                                                  

    try:
        os.symlink(finalpath, finallink)
        print('Symlinked {} to {}'.format(finalpath, finallink))
    except FileExistsError:
        print('Symlink exists. Removing and recreating it.')
        os.remove(finallink)
        os.symlink(finalpath, finallink)
        print('Symlinked {} to {}'.format(finalpath, finallink))
        os.symlink(finalpath, finallink)
        print('Symlinked {} to {}'.format(finalpath, finallink))
    


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Download latest released binary from a project on GitHub.')
    parser.add_argument('--token', help='GitHub API token', required=True)
    parser.add_argument('--username', help='GitHub username token', required=True)
    parser.add_argument('--org', help='GitHub organization project belongs to', required=True)
    parser.add_argument('--project', help='GitHub project to download latest binary from', required=True)
    parser.add_argument('--os', help='Operating system to download binary for (default is linux)', choices=['darwin', 'linux', 'windows'], default='linux')
    parser.add_argument('--arch', help='Architecture to download binary for (default is x86_64)', choices=['aarch64', 'armv7', 'i386', 'x86_64'], default='x86_64')
    parser.add_argument('--bindir', help='Directory to install binary into', required=True)
    parser.add_argument('--linkdir', help='Directory to install symlink into', required=True)
    args = vars(parser.parse_args())

    # todo
    # - linux-arm is not filtered out of list for generic linux
    # - need to be able to override binary name, or add additional binary, like e.g. for minikube
    # - need to be able to handle multiple binaries in a single release (kubectx)
    # - if no binary release (only source), can we detect and throw error?
    # - if no real release, but only pre-releases (like kn), can we do something?
    # - needs to read config file

    myos = args['os']
    myarch = args['arch']
    bindir = args['bindir']
    linkdir = args['linkdir']
    token = args['token']
    username = args['username']

    data = get_api_data(args['org'], args['project'])
    urls = get_latest_list(data)
    latest_version = get_latest_version(data)
    print("Latest version found: ", latest_version)
    print("Release URLs found: ")
    for url in urls:
        print(" - ", url)

    print("Filtered for {}, {}: ".format(myos, myarch))
    urls = filter_urls(urls, myarch, myos)
    for url in urls:
        print(" - ", url)

    print("Filtered for tarballs / zipfiles: ")
    urls = filter_extensions(urls, myos)
    for url in urls:
        print(" - ", url)

    print("Downloading and installing file: ")
    get_binary(urls, bindir, linkdir)