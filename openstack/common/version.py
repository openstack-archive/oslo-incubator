
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
Utilities for consuming the version from pkg_resources.
"""

import pkg_resources


class VersionInfo(object):

    def __init__(self, package):
        """Object that understands versioning for a package
        :param package: name of the python package, such as glance, or
                        python-glanceclient
        """
        self.package = package
        self.version = None
        self._cached_version = None

    def _get_version_from_pkg_resources(self):
        """Get the version of the package from the pkg_resources record
        associated with the package."""
        requirement = pkg_resources.Requirement.parse(self.package)
        provider = pkg_resources.get_provider(requirement)
        return provider.version

    def version_string(self):
        """Return the full version of the package including suffixes indicating
        VCS status.
        """
        if self.version is None:
            self.version = self._get_version_from_pkg_resources()

        return self.version

    # Compatibility functions
    canonical_version_string = version_string
    version_string_with_vcs = version_string

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
