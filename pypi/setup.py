#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# Copyright (c) 2012 OpenStack Foundation.
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

setuptools.setup(
    name='oslo',
    version='1',
    description="Namespace for common components for OpenStack",
    long_description="Namespace for common components for OpenStack",
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Environment :: No Input/Output (Daemon)',
        'Environment :: OpenStack',
    ],
    keywords='openstack',
    author='OpenStack',
    author_email='openstack@lists.openstack.org',
    url='http://www.openstack.org/',
    license='Apache Software License',
    zip_safe=True,
    packages=setuptools.find_packages(exclude=['ez_setup',
                                               'examples', 'tests']),
    namespace_packages=['oslo'],
)
