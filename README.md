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
usage: ghdl.py [-h] [--token TOKEN] [--username USERNAME] --org ORG --project PROJECT [--binary BINARY] [--os {darwin,linux,windows}] [--arch {aarch64,armv7l,i386,x86_64}]
               [--bindir BINDIR] [--linkdir LINKDIR] [--batch BATCH]

Download latest released binary from a project on GitHub. Defaults mentioned below are either auto-detected, like arch and os, or read from ~/.ghdl.ini.

optional arguments:
  -h, --help            show this help message and exit

Authenticate to GitHub (mandatory):
  --token TOKEN         GitHub API token; default is f659e51acee2558853dda7806524a327cf69bca1
  --username USERNAME   GitHub username token; default is wzzrd

List of organizations and projects for batch processing; if not specified, the --project and --org arguments are required:
  --batch BATCH         Yaml file with list of orgs / projects; default is False

Override autodetected arch and os:
  --os {darwin,linux,windows}
                        Operating system to download binary for; default is linux
  --arch {aarch64,armv7l,i386,x86_64}
                        Architecture to download binary for; default is x86_64

Specific organization and project name; if specified overrides --batch:
  --org ORG             GitHub organization project belongs to
  --project PROJECT     GitHub project to download latest binary from
  --binary BINARY       Override the binary name to download (optional)

Target directories for binaries and symlinks:
  --bindir BINDIR       Directory to install binary into; default is /home/mburgerh/Sync_Workstations/files
  --linkdir LINKDIR     Directory to install symlink into; default is /home/mburgerh/Sync_Workstations/links
```

### Authentication
The token and username arguments are required in order to provide GitHub with
API authentication. This should really not be required, because the rate
limit on the GitHub API is 60 requests per hour, which should be enough to
download a good amount of binaries through this script (it only hits the API
once per binary).

This requirement will be dropped in a future version.


### Specify organization, project and optionally the binary
Currently, the script will download the latest binary of the project specified by
a combination of the `--org`(anization), `--project` and (optionally)
`--binary` arguments.

The script can also read a YAML file containing a list of organization,
project and binary combinations. For an example, see the included
example.yaml file.

The YAML file can be specified on the commandline, with `--batch`, or in the
configuration file as the `batch` option in the `location` section.


### Override operating system and architecture
The script accepts three operating system arguments: darwin, linux and
windows. The operating system determines which binary to download, and
whether to opt for tarballs or zipfiles. The default operating system is
auto-detected.

The script accepts four architecture at the moment: aarch64, armv7, i386 and
x86\_64. Like the default operating system, the default architecture is
auto-detected.


### Target directories: bindir and linkdir
The script allows you to drop the downloaded binaries in a directory out of
sight somewhere. The example below uses `~/.local/gh`. This is specified by
the `bindir` argument. 

The binary is dropped into that directory, with the version number of the
binary appended to it. The script then creates a symlink into `linkdir`. The
example below uses `~/.local/bin` for that. Usually, that directory is part
of your `$PATH` or `$fish\_user\_paths`.

You can set both to the same directory as well, if you like.

Both `linkdir` and `bindir` can be set through the configuration file, in the
`location` section.

# Configuration file
A configuration file can be created at `~/.ghdl.ini` to simplify running
ghdl. The configuration file should follow this format:
```
[auth]
username = your_github_username
token = github_personal_access_token # only needs 'repo' scope

[location]
bindir = /home/you/.local/files
linkdir = /home/you/.local/links # add this to your path
batch = /home/you/.ghdl.yaml
```

# Batch file
Either on the command line, with the `--batch` option, or in the
configuration file, you can specify a YAML formatted file containing multiple
binaries to download. I have about 40 in mine, which makes it quite easy for
me to keep up to date with the latest version of e.g. starship, or minikube.

The batch file should have the following format:
```
- org: kubernetes
  project: minikube
- org: digitalocean
  project: doctl
- org: kubernetes
  project: minikube
  binary: docker-machine-driver-kvm2
```

The example above tells the script to download three binaries. The first two
are pretty much self-explanatory. The third overrides the binary name for the
minikube project to docker-machine-driver-kvm2. The minikube project provides
multiple binaries in their release, and we need both the minikube binary as
well as the docker-machine-driver-kvm2 binary.


# Example
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


# Known issues and roadmap

## Known issues
- for some projects, the selection system currently ends up with multiple binaries. For
  example, the kubebox project has both a binary that ends in 'linux', and one that ends
  in 'linux-arm'. The scripts selects the first hit right now ('linux'), but that's
  a bit hit and miss. 

- The script does not throw a useful error for projects that only have source releases.

- The script does not throw a useful error for projects that do not have final releases
  yet, but only pre-releases, like the knative client tooling. For these projects, the
  /releases/latest page does not exist in the API.

- When a project releases a new binary, the script will download the new binary and
  update the symlink. The old version is currently not removed.

- the GitHub release system is a complete and utter mess. GitHub does not
  seem to provide guidance to projects on how to release, and each project does
  their own thing. Therefore, what works today with this script can be broken
  tomorrow, or or even this afternoon.

- **the script is by no means perfect and will sometimes fail to download a
  binary or destroy civilization. Use at your own risk!**

## Short term roadmap
- clean up and refactor; script right now is a bit messy
- provide debug statements at useful places
- automatically remove old versions of a binary, if requested by the user
