# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
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

import __builtin__
import gettext
import logging
import unittest2 as unittest

import mock

from openstack.common import gettextutils


LOG = logging.getLogger(__name__)


class GettextTest(unittest.TestCase):

    def setUp(self):
        self._orig_gettext = None
        if '_' in __builtin__.__dict__:
            self._orig_gettext = __builtin__.__dict__['_']
            del __builtin__.__dict__['_']

    def tearDown(self):
        if self._orig_gettext:
            __builtin__.__dict__['_'] = self._orig_gettext

    def test_gettext_does_not_blow_up(self):
        from openstack.common.gettextutils import _
        LOG.info(_('test'))

    def test_install_gettext(self):
        gettextutils.install('test_install_gettext')
        self.assertIsInstance(__builtin__.__dict__['_'].__self__,
                              gettext.NullTranslations)

    def test_install_gettext_with_existed_translation(self):
        gettextutils.install('test_install_gettext')
        trans = __builtin__.__dict__['_'].__self__
        gettextutils.install('test_install_gettext')
        self.assertIs(__builtin__.__dict__['_'].__self__, trans)
        self.assertIsInstance(__builtin__.__dict__['_'].__self__._fallback,
                              gettext.NullTranslations)

    def test_install_gettext_with_existed_non_translation(self):
        __builtin__.__dict__['_'] = gettext.gettext
        gettextutils.install('test_install_gettext')
        self.assertEqual(__builtin__.__dict__['_'], gettext.gettext)
