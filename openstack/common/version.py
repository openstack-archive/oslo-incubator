# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import pkg_resources

from openstack.common import setup


def canonical_version_string(package, python_package=None, pre_version=None):
    if python_package is None:
        python_package = package
    requirement = pkg_resources.Requirement.parse(python_package)
    versioninfo = "%s/versioninfo" % package
    try:
        return pkg_resources.resource_string(requirement,
                                             versioninfo).strip()
    except (IOError, pkg_resources.DistributionNotFound):
        if pre_version is None:
            return setup.get_post_version(python_package)
        else:
            return setup.get_pre_version(python_package, pre_version)


def version_string(package, python_package=None, pre_version=None):
    version = canonical_version_string(package, python_package, pre_version)
    version_parts = version.split('~')
    if len(version_parts) == 1:
        return version_parts[0]
    else:
        return '%s-dev' % (version_parts[0],)
