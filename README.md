# ghdl

Python GitHub Downloader script to get the latest binary release from a GitHub project


## Overview

Lots of projects on GitHub release their software by providing pre-built binaries on
their releases page. If you work with a bunch of those, it can be challenging and
time-consuming to keep your binaries up to date. 

Package managers on Linux distros can help out for binaries that have been packaged as
an RPM or deb package, but not all useful binaries are packaged this way.

This script helps to keep these binaries up to date on your system by downloading the
latest available release from GitHub, installing it somewhere on your system and linking
the binary to some place in your $PATH.


## Usage
```
usage: ghdl.py [-h] --token TOKEN --username USERNAME --org ORG --project PROJECT
               [--os {darwin,linux,windows}] [--arch {aarch64,armv7,i386,x86_64}] --bindir BINDIR
               --linkdir LINKDIR

Download latest released binary from a project on GitHub.

optional arguments:
  -h, --help            show this help message and exit
  --token TOKEN         GitHub API token
  --username USERNAME   GitHub username token
  --org ORG             GitHub organization project belongs to
  --project PROJECT     GitHub project to download latest binary from
  --os {darwin,linux,windows}
                        Operating system to download binary for (default is linux)
  --arch {aarch64,armv7,i386,x86_64}
                        Architecture to download binary for (default is x86_64)
  --bindir BINDIR       Directory to install binary into
  --linkdir LINKDIR     Directory to install symlink into
```

### Authentication
The token and username arguments are required in order to provide GitHub with API
authentication. This should really be required, because the rate limit on the GitHub API
is 60 requests per hour, which should be enough to download a good amount of binaries
through this script (it only hits the API once per binary).

This requirement will be dropped in a future version.


### Binary specification
Currently, the script will download the latest binary of the project specified by
a combination of the org(anization) and project arguments. 

A future version will allow overriding the name of the binary to be downloaded from
a project. This would be useful for downloading the docker-machine driver from the
minikube project, for example.


### Operating system and architecture
The script accepts three operating system arguments: darwin, linux and windows. The
operating system determines which binary to download, and whether to opt for tarballs or
zipfiles. The default operating system is linux.

The script accepts four architecture at the moment: aarch64, armv7, i386 and x86\_64.
The x86\_64 architecture is the default and has received the most testing.

### bindir and linkdir
The script allows you to drop the downloaded binaries in a directory out of sight
somewhere. The example below uses `~/.local/gh`, for example. This is specified by the
`bindir` argument. The binary is dropped into that directory, withe the version number
of the binary appended to it. The script then creates a symlink into `linkdir`. The
example below uses `~/.local/bin` for that. Usually, that directory is part of your
`$PATH` or `$fish\_user\_paths`.

You can set both to the same directory as well, if you like.


## Example
```
./ghdl.py --token $github_token --username $username --bindir /home/you/.local/gh \
  --linkdir /home/you/.local/bin --org peco --project peco

URL:  https://api.github.com/repos/peco/peco/releases/latest
Latest version found:  v0.5.8
Release URLs found: 
 -  https://github.com/peco/peco/releases/download/v0.5.8/peco_darwin_amd64.zip
 -  https://github.com/peco/peco/releases/download/v0.5.8/peco_linux_386.tar.gz
 -  https://github.com/peco/peco/releases/download/v0.5.8/peco_linux_amd64.tar.gz
 -  https://github.com/peco/peco/releases/download/v0.5.8/peco_linux_arm.tar.gz
 -  https://github.com/peco/peco/releases/download/v0.5.8/peco_linux_arm64.tar.gz
 -  https://github.com/peco/peco/releases/download/v0.5.8/peco_windows_386.zip
 -  https://github.com/peco/peco/releases/download/v0.5.8/peco_windows_amd64.zip
Filtered for linux, x86_64: 
 -  https://github.com/peco/peco/releases/download/v0.5.8/peco_linux_amd64.tar.gz
Filtered for tarballs / zipfiles: 
 -  https://github.com/peco/peco/releases/download/v0.5.8/peco_linux_amd64.tar.gz
Downloading and installing file: 
Downloaded file: /tmp/tmp12pwrqxq/peco_linux_amd64.tar.gz
Largest file: /tmp/tmp12pwrqxq/peco_linux_amd64/peco
Cleaning up temporary directory
Symlinked /home/you/.local/gh/peco-v0.5.8 to /home/you/.local/bin/peco
```

The above example downloaded the released binary from the peco project. It chose the
gzipped tarball for x86\_64 Linux and dropped the file into `~/.local/gh` as
`peco-v0.5.8`. A symlink was created from there to `~/.local/bin/peco`.


## To do and known issues
- for some projects, the selection system currently ends up with multiple binaries. For
  example, the kubebox project has both a binary that ends in 'linux', and one that ends
  in 'linux-arm'. The scripts selects the first hit right now ('linux'), but that's
  a bit hit and miss. 

- it is currently not possible to override the name of the released binary; this would
  be useful to download the correct docker-machine driver for minikube, for example.

- projects like kubectx release multiple binaries in there releases (kubectx and kubens
  in this case, specifically). The script currently only handles a single binary
  download per release.

- The script does not throw a useful error for projects that only have source releases.

- The script does not throw a useful error for projects that do not have final releases
  yet, but only pre-releases, like the knative client tooling. For these projects, the
  /releases/latest page does not exist in the API.

- The script should be able to read a config file with the username, token, arch and os
  in it.

- The script should actually default to a detected operating system and architecture,
  instead of hard coded ones.

- When a project releases a new binary, the script will download the new binary and
  update the symlink. The old version is currently not removed.

## Short term roadmap
- configuration file usage
- process a list of binary / project sets to batch download binaries
- clean up and refactor variables names, etc.
- debug statements at useful places
- override the name of the binary
- automatically remove old versions of a binary, if requested by the user
- add tests for other operating systems / architectures
