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
import os

import setup


def _generate_version(python_package, pre_version):
    """Defer to the openstack.common.setup routines for making a
    version from git."""
    if pre_version is None:
        return setup.get_post_version(python_package)
    else:
        return setup.get_pre_version(python_package, pre_version)


def version_string_with_vcs(package, python_package=None, pre_version=None):
    """Return the full version of the package including suffixes indicating
    VCS status.

    For instance, if we are working towards the 2012.2 release,
    canonical_version_string should return 2012.2 if this is a final
    release, or else something like 2012.2~f1~20120705.20 if it's not.

    :param package: name of the top level python namespace. For glance, this
                    would be "glance" for python-glanceclient, it would be
                    "glanceclient"
    :param python_pacakge: optional name of the project name. For
                           glance this can be left unset. For
                           python-glanceclient, this would be
                           "python-glanceclient"
    :param pre_version: optional version that the project is working towards
    """
    if python_package is None:
        python_package = package
    if os.path.isdir(package) and os.path.isdir(".git"):
        return _generate_version(python_package, pre_version)
    requirement = pkg_resources.Requirement.parse(python_package)
    versioninfo = "%s/versioninfo" % package
    try:
        return pkg_resources.resource_string(requirement,
                                             versioninfo).strip()
    except (IOError, pkg_resources.DistributionNotFound):
        return _generate_version(python_package, pre_version)


def canonical_version_string(package, python_package=None, pre_version=None):
    """Return the simple version of the package excluding any suffixes.

    For instance, if we are working towards the 2012.2 release,
    canonical_version_string should return 2012.2 in all cases.

    :param package: name of the top level python namespace. For glance, this
                    would be "glance" for python-glanceclient, it would be
                    "glanceclient"
    :param python_pacakge: optional name of the project name. For
                           glance this can be left unset. For
                           python-glanceclient, this would be
                           "python-glanceclient"
    :param pre_version: optional version that the project is working towards
    """
    vcs_string = version_string_with_vcs(pacakge, python_package, pre_version)
    return vcs_string.split('~')[0]

def version_string(package, python_package=None, pre_version=None):
    """Return the base version of the package.

    For instance, if we are working towards the 2012.2 release,
    version_string should return 2012.2 if this is a final release, or
    2012.2-dev if it is not.

    :param package: name of the top level python namespace. For glance, this
                    would be "glance" for python-glanceclient, it would be
                    "glanceclient"
    :param python_pacakge: optional name of the project name. For
                           glance this can be left unset. For
                           python-glanceclient, this would be
                           "python-glanceclient"
    :param pre_version: optional version that the project is working towards
    """
    version = canonical_version_string(package, python_package, pre_version)
    version_parts = version.split('~')
    if len(version_parts) == 1:
        return version_parts[0]
    else:
        return '%s-dev' % (version_parts[0],)
