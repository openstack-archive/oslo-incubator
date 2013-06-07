#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010-2011 OpenStack Foundation
# All Rights Reserved.
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

"""Common utilities used in testing"""

import os
import tempfile
import sys

import fixtures
from oslo.config import cfg
import testtools

from openstack.common import exception
from openstack.common.fixture import moxstubout
from openstack.common import timeutils

CONF = cfg.CONF


class BaseTestCase(testtools.TestCase):

    def setUp(self):
        super(BaseTestCase, self).setUp()
        test_timeout = os.environ.get('OS_TEST_TIMEOUT', 0)
        try:
            test_timeout = int(test_timeout)
        except ValueError:
            # If timeout value is invalid do not set a timeout.
            test_timeout = 0
        if test_timeout > 0:
            self.useFixture(fixtures.Timeout(test_timeout, gentle=True))
        self.useFixture(fixtures.NestedTempfile())
        self.useFixture(fixtures.TempHomeDir())

        if (os.environ.get('OS_STDOUT_CAPTURE') == 'True' or
                os.environ.get('OS_STDOUT_CAPTURE') == '1'):
            stdout = self.useFixture(fixtures.StringStream('stdout')).stream
            self.useFixture(fixtures.MonkeyPatch('sys.stdout', stdout))
        if (os.environ.get('OS_STDERR_CAPTURE') == 'True' or
                os.environ.get('OS_STDERR_CAPTURE') == '1'):
            stderr = self.useFixture(fixtures.StringStream('stderr')).stream
            self.useFixture(fixtures.MonkeyPatch('sys.stderr', stderr))
        moxfixture = self.useFixture(moxstubout.MoxStubout())
        self.mox = moxfixture.mox
        self.stubs = moxfixture.stubs
        self.addCleanup(self._clear_attrs)
        self.addCleanup(CONF.reset)
        self.useFixture(fixtures.FakeLogger('openstack.common'))
        self.stubs.Set(exception, '_FATAL_EXCEPTION_FORMAT_ERRORS', True)
        self.tempdirs = []

    def tearDown(self):
        super(BaseTestCase, self).tearDown()
        CONF.reset()
        self.stubs.UnsetAll()
        self.stubs.SmartUnsetAll()

    def create_tempfiles(self, files, ext='.conf'):
        tempfiles = []
        for (basename, contents) in files:
            if not os.path.isabs(basename):
                (fd, path) = tempfile.mkstemp(prefix=basename, suffix=ext)
            else:
                path = basename + ext
                fd = os.open(path, os.O_CREAT | os.O_WRONLY)
            tempfiles.append(path)
            try:
                os.write(fd, contents)
            finally:
                os.close(fd)
        return tempfiles

    def config(self, **kw):
        """
        Override some configuration values.

        The keyword arguments are the names of configuration options to
        override and their values.

        If a group argument is supplied, the overrides are applied to
        the specified configuration option group.

        All overrides are automatically cleared at the end of the current
        test by the tearDown() method.
        """
        group = kw.pop('group', None)
        for k, v in kw.iteritems():
            CONF.set_override(k, v, group)

    def _clear_attrs(self):
        # Delete attributes that don't start with _ so they don't pin
        # memory around unnecessarily for the duration of the test
        # suite
        for key in [k for k in self.__dict__.keys() if k[0] != '_']:
            del self.__dict__[key]

    def flags(self, **kw):
        """Override flag variables for a test."""
        group = kw.pop('group', None)
        for k, v in kw.iteritems():
            CONF.set_override(k, v, group)


class ReplaceModule(fixtures.Fixture):
    """Replace a module with a fake module."""

    def __init__(self, name, new_value):
        self.name = name
        self.new_value = new_value

    def _restore(self, old_value):
        sys.modules[self.name] = old_value

    def setUp(self):
        super(ReplaceModule, self).setUp()
        old_value = sys.modules.get(self.name)
        sys.modules[self.name] = self.new_value
        self.addCleanup(self._restore, old_value)


class APICoverage(object):

    cover_api = None

    def test_api_methods(self):
        self.assertTrue(self.cover_api is not None)
        api_methods = [x for x in dir(self.cover_api)
                       if not x.startswith('_')]
        test_methods = [x[5:] for x in dir(self)
                        if x.startswith('test_')]
        self.assertThat(
            test_methods,
            testtools.matchers.ContainsAll(api_methods))


class TimeOverride(fixtures.Fixture):
    """Fixture to start and remove time override."""

    def setUp(self):
        super(TimeOverride, self).setUp()
        timeutils.set_time_override()
        self.addCleanup(timeutils.clear_time_override)
