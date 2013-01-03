
#    Copyright 2012 OpenStack LLC
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Utilities for consuming the auto-generated versioninfo files.
"""

import datetime
import pkg_resources
import os


def _run_shell_command(cmd):
    if os.name == 'nt':
        output = subprocess.Popen(["cmd.exe", "/C", cmd],
                                  stdout=subprocess.PIPE)
    else:
        output = subprocess.Popen(["/bin/sh", "-c", cmd],
                                  stdout=subprocess.PIPE)
    out = output.communicate()
    if len(out) == 0:
        return None
    if len(out[0].strip()) == 0:
        return None
    return out[0].strip()


def read_versioninfo(project):
    """Read the versioninfo file. If it doesn't exist, we're in a github
       zipball, and there's really no way to know what version we really
       are, but that should be ok, because the utility of that should be
       just about nil if this code path is in use in the first place."""
    versioninfo_path = os.path.join(project, 'versioninfo')
    if os.path.exists(versioninfo_path):
        with open(versioninfo_path, 'r') as vinfo:
            version = vinfo.read().strip()
    else:
        version = None
    return version


def write_versioninfo(project, version):
    """Write a simple file containing the version of the package."""
    with open(os.path.join(project, 'versioninfo'), 'w') as fil:
        fil.write("%s\n" % version)


class VersionInfo(object):

    def __init__(self, package, python_package=None, pre_version=None):
        """Object that understands versioning for a package
        :param package: name of the top level python namespace. For glance,
                        this would be "glance" for python-glanceclient, it
                        would be "glanceclient"
        :param python_package: optional name of the project name. For
                               glance this can be left unset. For
                               python-glanceclient, this would be
                               "python-glanceclient"
        :param pre_version: optional version that the project is working to
        """
        self.package = package
        if python_package is None:
            self.python_package = package
        else:
            self.python_package = python_package
        self.version = None
        self._cached_version = None

    def _generate_version(self):
        """Return a version which is equal to the tag that's on the current
        revision if there is one, or tag plus number of additional revisions
        if the current revision has no tag."""

        version = read_versioninfo(self.python_package)
        if not version and os.path.isdir('.git'):
            version = _run_shell_command(
                "git describe --always").replace('-', '.')
            write_versioninfo(self.python_package, version)
        return version

    def version_string_with_vcs(self, always=False):
        """Return the full version of the package including suffixes indicating
        VCS status.

        For instance, if we are working towards the 2012.2 release,
        canonical_version_string should return 2012.2 if this is a final
        release, or else something like 2012.2~f1~20120705.20 if it's not.

        :param always: if true, skip all version caching
        """
        if always:
            self.version = self._generate_version()

        if self.version is None:

            requirement = pkg_resources.Requirement.parse(self.python_package)
            versioninfo = "%s/versioninfo" % self.package
            try:
                self.version = pkg_resources.resource_string(requirement,
                                                             versioninfo)
            except (IOError, pkg_resources.DistributionNotFound):
                self.version = self._generate_version()

        return self.version

    def canonical_version_string(self, always=False):
        """Return the simple version of the package excluding any suffixes.

        For instance, if we are working towards the 2012.2 release,
        canonical_version_string should return 2012.2 in all cases.

        :param always: if true, skip all version caching
        """
        return self.version_string_with_vcs(always).split('~')[0]

    def version_string(self, always=False):
        """Return the base version of the package.

        For instance, if we are working towards the 2012.2 release,
        version_string should return 2012.2 if this is a final release, or
        2012.2-dev if it is not.

        :param always: if true, skip all version caching
        """
        version_parts = self.version_string_with_vcs(always).split('~')
        if len(version_parts) == 1:
            return version_parts[0]
        else:
            return '%s-dev' % (version_parts[0],)

    def cached_version_string(self, prefix=""):
        """Generate an object which will expand in a string context to
        the results of version_string(). We do this so that don't
        call into pkg_resources every time we start up a program when
        passing version information into the CONF constructor, but
        rather only do the calculation when and if a version is requested
        """
        if not self._cached_version:
            self._cached_version = "%s%s" % (prefix,
                                             self.version_string())
        return self._cached_version
