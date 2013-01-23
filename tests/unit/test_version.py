# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
# Copyright 2012-2013 Hewlett-Packard Development Company, L.P.
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
import StringIO
import sys
import tempfile
import testtools

import stubout

from openstack.common.cfg import *
from openstack.common import version


class BaseTestCase(testtools.TestCase):

    def setUp(self):
        super(BaseTestCase, self).setUp()
        self.stubs = stubout.StubOutForTesting()
        self.addCleanup(self.stubs.UnsetAll)


class DeferredVersionTestCase(BaseTestCase):

    def setUp(self):
        super(DeferredVersionTestCase, self).setUp()
        self.conf = ConfigOpts()

    def test_cached_version(self):
        class MyVersionInfo(version.VersionInfo):
            def _get_version_from_pkg_resources(self):
                return "5.5.5.5"

        deferred_string = MyVersionInfo("openstack").\
            cached_version_string()
        self.conf([], project="project", prog="prog", version=deferred_string)
        self.assertEquals("5.5.5.5", str(self.conf.version))

    def test_print_cached_version(self):
        class MyVersionInfo(version.VersionInfo):
            def _get_version_from_pkg_resources(self):
                return "5.5.5.5"

        deferred_string = MyVersionInfo("openstack")\
            .cached_version_string()
        self.stubs.Set(sys, 'stderr', StringIO.StringIO())
        self.assertRaises(SystemExit,
                          self.conf, ['--version'],
                          project="project",
                          prog="prog",
                          version=deferred_string)
        self.assertEquals("5.5.5.5", sys.stderr.getvalue().strip())

    def test_print_cached_version_with_long_string(self):
        my_version = "11111222223333344444555556666677777888889999900000"

        class MyVersionInfo(version.VersionInfo):
            def _get_version_from_pkg_resources(self):
                return my_version

        deferred_string = MyVersionInfo("openstack")\
            .cached_version_string()

        for i in range(50):
            self.stubs.Set(sys, 'stderr', StringIO.StringIO())
            self.assertRaises(SystemExit,
                              self.conf, ['--version'],
                              project="project",
                              prog="prog",
                              version=deferred_string)
            self.assertEquals(my_version, sys.stderr.getvalue().strip())
