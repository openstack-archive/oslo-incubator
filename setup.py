#!/usr/bin/python
# -*- encoding: utf-8 -*-
# Copyright (c) 2012 OpenStack, LLC.
# Copyright (c) 2012-2013 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import setuptools

from openstack.common import setup

requires = setup.parse_requirements()
depend_links = setup.parse_dependency_links()
package = 'openstack.common'

filters = [
    "AvailabilityZoneFilter = "
    "openstack.common.scheduler.filters."
    "availability_zone_filter:AvailabilityZoneFilter",
    "CapabilitiesFilter = "
    "openstack.common.scheduler.filters."
    "capabilities_filter:CapabilitiesFilter",
    "JsonFilter = "
    "openstack.common.scheduler.filters.json_filter:JsonFilter",
]

weights = [
    "FakeWeigher1 = tests.unit.fakes:FakeWeigher1",
    "FakeWeigher2 = tests.unit.fakes:FakeWeigher2",
]

setuptools.setup(
    name=package,
    version=setup.get_version(package, '2013.1'),
    description="Common components for Openstack",
    long_description="Common components for Openstack "
                     "including paster templates.",
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.6',
        'Environment :: No Input/Output (Daemon)', ],
    keywords='openstack',
    author='OpenStack',
    author_email='openstack@lists.launchpad.net',
    url='http://www.openstack.org/',
    license='Apache Software License',
    packages=setuptools.find_packages(exclude=['ez_setup',
                                               'examples', 'tests']),
    include_package_data=True,
    cmdclass=setup.get_cmdclass(),
    zip_safe=True,
    install_requires=requires,
    dependency_links=depend_links,
    entry_points={
        "openstack.common.scheduler.filters": filters,
        "openstack.common.tests.fakes.weights": weights,
    },
    namespace_packages=['openstack'],
)
