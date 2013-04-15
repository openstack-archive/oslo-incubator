# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
# All Rights Reserved.
# Copyright 2013 IBM Corp.
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

import gettext
import logging

import mock
import mox

from openstack.common import gettextutils
from tests import utils


LOG = logging.getLogger(__name__)


class GettextTest(utils.BaseTestCase):

    def test_gettext_does_not_blow_up(self):
        LOG.info(gettextutils._('test'))

    def test_gettext_install_looks_up_localedir(self):
        with mock.patch('os.environ.get') as environ_get:
            with mock.patch('gettext.install') as gettext_install:
                environ_get.return_value = '/foo/bar'

                gettextutils.install('blaa')

                environ_get.assert_called_once_with('BLAA_LOCALEDIR')
                gettext_install.assert_called_once_with('blaa',
                                                        localedir='/foo/bar',
                                                        unicode=True)


class MessageTestCase(utils.BaseTestCase):
    """Unit tests for locale Message class."""

    def setUp(self):
        super(MessageTestCase, self).setUp()
        self._lazy_gettext = gettextutils.get_lazy_gettext('oslo')
        self.mox = mox.Mox()

    def tearDown(self):
        self.mox.UnsetStubs()
        super(MessageTestCase, self).tearDown()

    def test_localize_creates_new_message(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        self.assertEqual(result, msgid)

    def test_localize_with_params(self):
        msgid = "Some string with params: %s"

        result = self._lazy_gettext(msgid)

        self.assertEqual(result.message, msgid)

    def test_localize_on_string(self):
        msgid = "Some string with params: %s"
        params = (0, )

        message = msgid % params

        result = self._lazy_gettext(msgid) % params
        # simulate writing out as string
        result_str = '%s' % result

        self.assertEqual(result_str, message)

    def test_regex_find_named_parameters(self):
        msgid = ("%(description)s\nCommand: %(cmd)s\n"
                 "Exit code: %(exit_code)s\nStdout: %(stdout)r\n"
                 "Stderr: %(stderr)r %%(something)s")
        params = {'description': 'test1',
                  'cmd': 'test2',
                  'exit_code': 'test3',
                  'stdout': 'test4',
                  'stderr': 'test5',
                  'something': 'trimmed'}

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, msgid % params)

    def test_localize_with_dec_params(self):
        """Verify we can inject numbers into Messages."""
        msgid = "Some string with params: %d"
        params = [0, 1, 10, 24124]

        messages = []
        results = []
        for param in params:
            messages.append(msgid % param)
            results.append(self._lazy_gettext(msgid) % param)

        for message, result in zip(messages, results):
            self.assertEqual(type(result), gettextutils.Message)
            self.assertEqual(result, message)

            # simulate writing out as string
            result_str = '%s' % result
            self.assertEqual(result_str, message)

    def test_localize_extra_params(self):
        msgid = "Some string with params: %(param1)s %(param2)s"
        params = {'param1': 'test',
                  'param2': 'test2',
                  'param3': 'trimmed'}

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, msgid % params)

    def test_localize_object_param_copied(self):
        some_obj = SomeObject()
        some_obj.tag = 'stub_object'
        msgid = "Found object: %(some_obj)s"

        result = self._lazy_gettext(msgid) % {'some_obj': some_obj}

        some_obj.tag = 'switched_tag'

        self.assertEqual(result, msgid % {'some_obj': 'stub_object'})

    def test_localize_object_param_to_repr(self):
        some_obj = SomeObject()
        some_obj.tag = 'stub_object'
        msgid = "Found object: %(some_obj)r"

        result = self._lazy_gettext(msgid) % {'some_obj': some_obj}

        message = msgid % {'some_obj': some_obj}
        result_str = '%s' % result

        self.assertEqual(result_str, message)

    def test_interpolation_missing_param(self):
        msgid = ("Some string with params: %(param1)s %(param2)s"
                 " and a missing one %(missing)s")
        params = {'param1': 'test',
                  'param2': 'test2'}

        test_me = lambda: self._lazy_gettext(msgid) % params

        self.assertRaises(KeyError, test_me)

    def test_operator_add(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        additional = " with more added"
        expected = msgid + additional
        result = result + additional

        self.assertEqual(type(result), gettextutils.Message)
        self.assertEqual(result, expected)

    def test_operator_radd(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        additional = " with more added"
        expected = additional + msgid
        result = additional + result

        self.assertEqual(type(result), gettextutils.Message)
        self.assertEqual(result, expected)

    def test_get_index(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        expected = 'm'
        result = result[2]

        self.assertEqual(result, expected)

    def test_getitem_string(self):
        """Verify using string indexes on Message does not work."""
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        test_me = lambda: result['blah']

        self.assertRaises(TypeError, test_me)

    def test_contains(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        self.assertIn('msgid', result)
        self.assertNotIn('blah', result)

    def test_locale_set_does_translation(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)
        result.locale = 'test_locale'

        self.mox.StubOutWithMock(gettext, 'translation')
        fake_lang = self.mox.CreateMock(gettext.GNUTranslations)

        gettext.translation('oslo', languages=['test_locale'],
                            fallback=True).AndReturn(fake_lang)
        fake_lang.ugettext(msgid).AndReturn(msgid)

        self.mox.ReplayAll()

        result = result.message

        self.mox.VerifyAll()

        self.assertEqual(msgid, result)


class SomeObject(object):

    def __init__(self, tag='default'):
        self.tag = tag

    def __repr__(self):
        # since we copy the object in the Message
        # the default python __repr__ will not be
        # the same, as it really isn't the same object
        # when % (format) was called
        return str(self.__dict__)

    def __str__(self):
        return self.tag

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state):
        for (k, v) in state.items():
            setattr(self, k, v)
