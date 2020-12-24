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
import platform
import configparser

from zipfile import ZipFile
from pathlib import Path


def get_api_data(org, project):
    """
    Get information on the latest version of a project on GitHub through the API
    """

    url = "https://api.github.com/repos/{}/{}/releases/latest".format(
        org, project)
    print("URL: ", url)

    credentials = "%s:%s" % (username, token)
    encoded_credentials = base64.b64encode(credentials.encode("ascii"))

    try:
        req = urllib.request.Request(url)
        req.add_header("Authorization",
                       "Basic %s" % encoded_credentials.decode("ascii"))
        response = urllib.request.urlopen(req)
    except:
        print("Cannot open {}".format(url))
        sys.exit(1)

    response_data = response.read()
    json_data = json.loads(response_data)

    return json_data


def get_latest_list(data):
    """
    Get list of download URLs from blob of API data
    """

    links = []
    for asset in data["assets"]:
        links.append(asset["browser_download_url"])

    return links


def filter_urls(urls, myArch, myOS, myBinary=None):
    """
    Filters list of URLs to only include those for the requested OS and architecture
    Optionally, the myBinary parameter can override the binary name we are filtering for
    """

    original_urls = urls.copy()
    if myBinary != None:
        bin_r = re.compile(".*{}.*".format(binary))
        urls = [x for x in urls if bin_r.match(x, re.IGNORECASE)]
        if len(urls) == original_urls or len(urls) == 0:
            urls = original_urls
    
    original_urls = urls.copy()
    os_r = re.compile(".*{}.*".format(myOS))
    urls = [x for x in urls if os_r.match(x, re.IGNORECASE)]
    if len(urls) == original_urls or len(urls) == 0:
        urls = original_urls

    # ? are these regexps exhaustive enough?
    # ? I'm not even sure arm(v)8 is actually used in releases :)
    # * Checked on couple of rpis; it's aarch64, armv7l and armv6l
    # * I don't think I want to support armv6l, but armv7l seems reasonable to support
    original_urls = urls.copy()
    if myArch == "x86_64":
        arch_r = re.compile(".*64bit.*|.*x86_64.*|.*amd64.*")
    elif myArch == "aarch64":
        arch_r = re.compile(".*aarch64.*|.*arm64.*|.*arm8.*|.*armv8.*")
    elif myArch == "armv7l":
        # Assumption is that plain 'arm' refers to armv7l
        arch_r = re.compile(".*armv7.*|.*arm7.*|.*arm")
    elif myArch == "i386":
        arch_r = re.compile(".*386.*")

    urls = [x for x in urls if arch_r.match(x, re.IGNORECASE)]

    if len(urls) == original_urls or len(urls) == 0:
        urls = original_urls

    return urls


def filter_binary(urls, binary):
    """
    Filters list of URLs to only those files with the right name
    If list ends up empty, returns the original list.
    # * should actually raise error / throw exception, I suppose
    """

    bin_r = re.compile(".*{}.*".format(binary))

    new_urls = [x for x in urls if bin_r.match(x, re.IGNORECASE)]

    if len(new_urls) == 0 and len(urls) > 0:
        return urls
    else:
        return new_urls


def filter_extensions(urls, myOS):
    """
    Filters list of URLs to only those files with the right extension
    Prefers tarballs for Linux and MacOS, zipfiles for Windows
    If list ends up empty, returns the original list.
    """

    # Filter useless extensions, like for checksums, text files, debs, rpms...
    ext_r = re.compile(
        ".*asc|.*sha512.*|.*md5.*|.*sha1.*|.*sha2*|.*txt|.*deb|.*rpm")
    urls = [x for x in urls if not ext_r.match(x, re.IGNORECASE)]

    if myOS == "linux" or myOS == "darwin":
        # ? what if a project releases both a tar.gz and a tar.xz?
        # ? what if a project releases a non-zipped tarball?
        ext_r = re.compile(".*tar.gz|.*tar.xz|.*tar.bz|.*tar.bz2")
    elif myOS == "windows":
        ext_r = re.compile(".*zip")

    new_urls = [x for x in urls if ext_r.match(x, re.IGNORECASE)]

    if len(new_urls) == 0 and len(urls) > 0:
        return urls
    else:
        return new_urls


def get_latest_version(data):
    """
    Get the version of the latest release, based on list of URLs
    """

    return data["tag_name"]


def get_binary(urls, bindir, linkdir):
    """
    Download the latest version of the binary and handle it, by dropping the actual binary into bindir, and a symlink to that binary into linkdir
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
    targetfile = tmpdir + "/" + name
    urllib.request.urlretrieve(url, targetfile)
    print("Downloaded file: " + tmpdir + "/" + name)
    os.chdir(tmpdir)

    extracted = False
    if "tar" in name:
        mytar = tarfile.open(targetfile)
        mytar.extractall()
        os.remove(targetfile)
        extracted = True
    elif "zip" in name:
        with ZipFile(targetfile, "r") as myzip:
            myzip.extractall()
        os.remove(targetfile)
        extracted = True
    else:
        print("name was {}, no tar or zip?".format(name))

    if extracted:
        # Find largest file in extracted directory
        largest = sorted(
            (os.path.getsize(s), s)
            for s in glob.glob(tmpdir + "/**", recursive=True))[-1][1]
        print("Largest file: {}".format(largest))

        finalfile = os.path.basename(largest).replace("_", "-").split("-")[0]
        finalpath = bindir + "/" + finalfile + "-" + latest_version
        shutil.move(largest, finalpath)
    else:
        if binary != None:
            print("Binary is not none")
            finalfile = binary.replace("_", "-")
        else:
            finalfile = os.path.basename(targetfile).replace("_", "-")
        finalpath = bindir + "/" + finalfile + "-" + latest_version
        shutil.move(targetfile, finalpath)

    finallink = linkdir + "/" + finalfile
    os.chmod(finalpath, 0o755)
    print("Cleaning up temporary directory")
    shutil.rmtree(tmpdir)

    try:
        os.symlink(finalpath, finallink)
        print("Symlinked {} to {}".format(finalpath, finallink))
    except FileExistsError:
        print("Symlink exists. Removing and recreating it.")
        os.remove(finallink)
        os.symlink(finalpath, finallink)
        print("Symlinked {} to {}".format(finalpath, finallink))


if __name__ == "__main__":

    default_arch = platform.machine().lower()
    default_os = platform.system().lower()

    # Config file handling
    home_dir = str(Path.home())
    cp = configparser.ConfigParser()
    config_file = '{}/.ghdl.ini'.format(home_dir)
    cp.read(config_file)

    # handling of ['auth'] section in ghdl.ini
    token_required = username_required = True
    token = username = ""
    if "token" in cp["auth"]:
        token = cp["auth"]["token"]
        token_required = False

    if "username" in cp["auth"]:
        username = cp["auth"]["username"]
        username_required = False

    # handling of ['location'] section in ghdl.ini
    linkdir_required = bindir_required = True
    linkdir = bindir = None
    if "linkdir" in cp["location"]:
        print("yes")
        linkdir = cp["location"]["linkdir"]
        linkdir_required = False
    if "bindir" in cp["location"]:
        bindir = cp["location"]["bindir"]
        bindir_required = False

    print("debug: ")
    print(linkdir)
    print(bindir)

    # Argument handling
    # * need to rearrange these in a more logical order
    parser = argparse.ArgumentParser(
        description="Download latest released binary from a project on GitHub."
    )
    parser.add_argument("--token",
                        help="GitHub API token; default is {}".format(token),
                        required=token_required,
                        default=token)
    parser.add_argument(
        "--username",
        help="GitHub username token; default is {}".format(username),
        required=username_required,
        default=username)
    parser.add_argument("--org",
                        help="GitHub organization project belongs to",
                        required=True)
    parser.add_argument("--project",
                        help="GitHub project to download latest binary from",
                        required=True)
    parser.add_argument("--binary",
                        help="Override the binary name to download (optional)",
                        default=None,
                        required=False)
    parser.add_argument(
        "--os",
        help="Operating system to download binary for; default is {}".format(
            default_os),
        choices=["darwin", "linux", "windows"],
        default=default_os,
    )
    parser.add_argument(
        "--arch",
        help="Architecture to download binary for; default is {}".format(
            default_arch),
        choices=["aarch64", "armv7l", "i386", "x86_64"],
        default=default_arch,
    )
    parser.add_argument(
        "--bindir",
        help="Directory to install binary into; default is {}".format(
            bindir if bindir != None else None),
        required=False if bindir != None else True,
        default=bindir if bindir != None else None)
    parser.add_argument(
        "--linkdir",
        help="Directory to install symlink into; default is {}".format(
            linkdir if linkdir != None else None),
        required=False if linkdir != None else True,
        default=linkdir if linkdir != None else None)
    args = vars(parser.parse_args())

    # The else case below should never happen, because
    # platform.system().lower() should always return either linux, windows or
    # darwin...
    myos = args["os"]
    # The else case below should never happen, because
    # platform.machine().lower() should always return something like x86_64 or aarch64
    myarch = args["arch"]
    bindir = args["bindir"]
    linkdir = args["linkdir"]
    token = args["token"]
    username = args["username"]
    binary = args["binary"]

    data = get_api_data(args["org"], args["project"])
    urls = get_latest_list(data)
    latest_version = get_latest_version(data)
    print("Latest version found: ", latest_version)
    print("Release URLs found: ")
    for url in urls:
        print(" - ", url)

    print("Filtered for {}, {}: ".format(myos, myarch))
    urls = filter_urls(urls, myarch, myos, myBinary=binary)
    for url in urls:
        print(" - ", url)

    print("Filtered for tarballs / zipfiles: ")
    urls = filter_extensions(urls, myos)
    for url in urls:
        print(" - ", url)

    print("Downloading and installing file: ")
    get_binary(urls, bindir, linkdir)
