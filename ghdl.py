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
import yaml

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
        bin_r = re.compile(".*{}.*".format(myBinary), re.IGNORECASE)
        urls = [x for x in urls if bin_r.match(x)]
        if len(urls) == len(original_urls) or len(urls) == 0:
            print(len(urls))
            urls = original_urls

    original_urls = urls.copy()
    os_r = re.compile(".*{}.*".format(myOS), re.IGNORECASE)
    urls = [x for x in urls if os_r.match(x)]
    if len(urls) == len(original_urls) or len(urls) == 0:
        urls = original_urls

    # ? are these regexps exhaustive enough?
    # ? I'm not even sure arm(v)8 is actually used in releases :)
    # * Checked on couple of rpis; it's aarch64, armv7l and armv6l
    # * I don't think I want to support armv6l, but armv7l seems reasonable to support
    original_urls = urls.copy()
    if myArch == "x86_64":
        arch_r = re.compile(".*64bit.*|.*x86_64.*|.*amd64.*", re.IGNORECASE)
    elif myArch == "aarch64":
        arch_r = re.compile(".*aarch64.*|.*arm64.*|.*arm8.*|.*armv8.*", re.IGNORECASE)
    elif myArch == "armv7l":
        # Assumption is that plain 'arm' refers to armv7l
        arch_r = re.compile(".*armv7.*|.*arm7.*|.*arm", re.IGNORECASE)
    elif myArch == "i386":
        arch_r = re.compile(".*386.*", re.IGNORECASE)

    urls = [x for x in urls if arch_r.match(x)]

    if len(urls) == original_urls or len(urls) == 0:
        urls = original_urls

    return urls


def filter_binary(urls, binary):
    """
    Filters list of URLs to only those files with the right name
    If list ends up empty, returns the original list.
    # * should actually raise error / throw exception, I suppose
    """

    bin_r = re.compile(".*{}.*".format(binary), re.IGNORECASE)

    new_urls = [x for x in urls if bin_r.match(x)]

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
        ".*asc|.*sha512.*|.*md5.*|.*sha1.*|.*sha2*|.*txt|.*deb|.*rpm", re.IGNORECASE)
    urls = [x for x in urls if not ext_r.match(x)]

    if myOS == "linux" or myOS == "darwin":
        # ? what if a project releases both a tar.gz and a tar.xz?
        # ? what if a project releases a non-zipped tarball?
        ext_r = re.compile(".*tar.gz|.*tar.xz|.*tar.bz|.*tar.bz2", re.IGNORECASE)
    elif myOS == "windows":
        ext_r = re.compile(".*zip")

    new_urls = [x for x in urls if ext_r.match(x)]

    if len(new_urls) == 0 and len(urls) > 0:
        return urls
    else:
        return new_urls


def get_latest_version(data):
    """
    Get the version of the latest release, based on list of URLs
    """

    return data["tag_name"]


def get_basic_filename(name, latest_version):
    """
    Get the plain name of the binary, with operating system name, architecture and version stipped off
    """

    pattern = re.compile(
        "[-_]amd64|[-_]x86_64|[-_]64bit|[-_]aarch64|[-_]arm64|[-_]arm8|[-_]armv8|[-_]armv7l|[-_]386|[-_]i386",
        re.IGNORECASE)
    name = re.sub(pattern, "", name)

    pattern = re.compile("[-_]windows|[-_]linux|[-_]darwin", re.IGNORECASE)
    name = re.sub(pattern, "", name)

    pattern = re.compile(
        "[-_]{}|[-_]{}".format(latest_version,
                               latest_version.removeprefix('v')),
        re.IGNORECASE)
    name = re.sub(pattern, "", name)

    return name


def get_binary(urls, bindir, linkdir, latest_version):
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
        finalfile = get_basic_filename(finalfile, latest_version)
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

def handle_item(org, project, myarch, myos, binary=None):
    data = get_api_data(org, project)
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
    get_binary(urls, bindir, linkdir, latest_version)


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
    # ! we need to check for cp["auth"] before we do this, otherwise configparser errors
    # out on us
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
        linkdir = cp["location"]["linkdir"]
        linkdir_required = False
    if "bindir" in cp["location"]:
        bindir = cp["location"]["bindir"]
        bindir_required = False
    if "batch" in cp["location"]:
        batch= cp["location"]["batch"]
    else:
        batch = False

    # Argument handling
    # * need to rearrange these in a more logical order
    parser = argparse.ArgumentParser(
        description="""Download latest released binary from a project on GitHub.
        Defaults mentioned below are either auto-detected, like arch and os, 
        or read from ~/.ghdl.ini."""
    )
    group_auth = parser.add_argument_group("Authenticate to GitHub (mandatory)")
    group_batch = parser.add_argument_group("List of organizations and projects for batch processing; if not specified, the --project and --org arguments are required")
    group_autodetect = parser.add_argument_group("Override autodetected arch and os")
    group_specific = parser.add_argument_group("Specific organization and project name; if specified overrides --batch")
    group_locations = parser.add_argument_group("Target directories for binaries and symlinks")

    group_auth.add_argument("--token",
                        help="GitHub API token; default is {}".format(token),
                        required=token_required,
                        default=token)
    group_auth.add_argument(
        "--username",
        help="GitHub username token; default is {}".format(username),
        required=username_required,
        default=username)
    group_specific.add_argument("--org",
                        help="GitHub organization project belongs to",
                        required='--batch' not in sys.argv and not batch)
    group_specific.add_argument("--project",
                        help="GitHub project to download latest binary from",
                        required='--batch' not in sys.argv and not batch)
    group_specific.add_argument("--binary",
                        help="Override the binary name to download (optional)",
                        default=None,
                        required=False)
    group_autodetect.add_argument(
        "--os",
        help="Operating system to download binary for; default is {}".format(
            default_os),
        choices=["darwin", "linux", "windows"],
        default=default_os,
    )
    group_autodetect.add_argument(
        "--arch",
        help="Architecture to download binary for; default is {}".format(
            default_arch),
        choices=["aarch64", "armv7l", "i386", "x86_64"],
        default=default_arch,
    )
    group_locations.add_argument(
        "--bindir",
        help="Directory to install binary into; default is {}".format(
            bindir if bindir != None else None),
        required=False if bindir != None else True,
        default=bindir if bindir != None else None)
    group_locations.add_argument(
        "--linkdir",
        help="Directory to install symlink into; default is {}".format(
            linkdir if linkdir != None else None),
        required=False if linkdir != None else True,
        default=linkdir if linkdir != None else None)
    group_batch.add_argument(
        "--batch",
        help="Yaml file with list of orgs / projects; default is {}".format(
            batch if batch != None else None),
        required=False,
        default=batch if batch != None else None)

    args = vars(parser.parse_args())

    myos = args["os"]
    myarch = args["arch"]
    bindir = args["bindir"]
    linkdir = args["linkdir"]
    token = args["token"]
    username = args["username"]
    binary = args["binary"]
    batch= args["batch"]
    org = args["org"]
    project = args["project"]

    if org and project:
        handle_item(org, project, myarch, myos, binary)
    elif batch:
        with open(batch) as f:
            entries = yaml.load(f, Loader=yaml.FullLoader)
        for item in entries:
            if "binary" in item:
                handle_item(item["org"], item["project"], myarch, myos, binary=item["binary"])
            else:
                handle_item(item["org"], item["project"], myarch, myos)
    else:
        print("Apparently, neither --batch nor --org and --project were specified.")
        sys.exit(1)
