# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
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

import os
import shutil
import sys
import StringIO
import tempfile
import unittest

import stubout

from openstack.common.cfg import *
from openstack.common import version


class BaseTestCase(unittest.TestCase):

    def setUp(self):
        self.stubs = stubout.StubOutForTesting()

    def tearDown(self):
        self.stubs.UnsetAll()


class DeferredVersionTestCase(BaseTestCase):

    def setUp(self):
        super(DeferredVersionTestCase, self).setUp()
        self.conf = ConfigOpts()

    def test_deferred_version(self):
        class MyVersionInfo(version.VersionInfo):
            def _generate_version(self):
                return "5.5.5.5"

        deferred_string = MyVersionInfo("openstack").\
            deferred_version_string()
        self.conf([], project="project", prog="prog", version=deferred_string)
        self.assertEquals("5.5.5.5", str(self.conf.version))

    def test_print_deferred_version(self):
        class MyVersionInfo(version.VersionInfo):
            def _generate_version(self):
                return "5.5.5.5"

        deferred_string = MyVersionInfo("openstack")\
            .deferred_version_string()
        self.stubs.Set(sys, 'stderr', StringIO.StringIO())
        self.assertRaises(SystemExit,
                          self.conf, ['--version'],
                          project="project",
                          prog="prog",
                          version=deferred_string)
        self.assertEquals("5.5.5.5", sys.stderr.getvalue().strip())
