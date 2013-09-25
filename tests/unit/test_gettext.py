# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
# Copyright 2013 IBM Corp.
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

from babel import localedata
import copy
import gettext
import logging
import logging.handlers
import os

import mock
import six

from openstack.common.fixture import moxstubout
from openstack.common import gettextutils
from openstack.common import test

LOG = logging.getLogger(__name__)


class GettextTest(test.BaseTestCase):

    def setUp(self):
        super(GettextTest, self).setUp()
        moxfixture = self.useFixture(moxstubout.MoxStubout())
        self.stubs = moxfixture.stubs
        self.mox = moxfixture.mox
        # remember so we can reset to it later
        self._USE_LAZY = gettextutils.USE_LAZY

    def tearDown(self):
        # reset to value before test
        gettextutils.USE_LAZY = self._USE_LAZY
        super(GettextTest, self).tearDown()

    def test_enable_lazy(self):
        gettextutils.USE_LAZY = False

        gettextutils.enable_lazy()
        # assert now enabled
        self.assertTrue(gettextutils.USE_LAZY)

    def test_underscore_non_lazy(self):
        # set lazy off
        gettextutils.USE_LAZY = False

        if six.PY3:
            self.mox.StubOutWithMock(gettextutils._t, 'gettext')
            gettextutils._t.gettext('blah').AndReturn('translated blah')
        else:
            self.mox.StubOutWithMock(gettextutils._t, 'ugettext')
            gettextutils._t.ugettext('blah').AndReturn('translated blah')
        self.mox.ReplayAll()

        result = gettextutils._('blah')
        self.assertEqual('translated blah', result)

    def test_underscore_lazy(self):
        # set lazy off
        gettextutils.USE_LAZY = False

        gettextutils.enable_lazy()
        result = gettextutils._('blah')
        self.assertIsInstance(result, gettextutils.Message)

    def test_gettext_does_not_blow_up(self):
        LOG.info(gettextutils._('test'))

    def test_gettextutils_install(self):
        gettextutils.install('blaa')
        self.assertTrue(isinstance(_('A String'), six.text_type))  # noqa

        gettextutils.install('blaa', lazy=True)
        self.assertTrue(isinstance(_('A Message'),  # noqa
                                   gettextutils.Message))

    def test_gettext_install_looks_up_localedir(self):
        with mock.patch('os.environ.get') as environ_get:
            with mock.patch('gettext.install') as gettext_install:
                environ_get.return_value = '/foo/bar'

                gettextutils.install('blaa')

                environ_get.assert_called_once_with('BLAA_LOCALEDIR')
                if six.PY3:
                    gettext_install.assert_called_once_with(
                        'blaa',
                        localedir='/foo/bar')
                else:
                    gettext_install.assert_called_once_with(
                        'blaa',
                        localedir='/foo/bar',
                        unicode=True)

    def test_is_basestring_instance(self):
        if not six.PY3:
            message = gettextutils.Message('test', 'test_domain')
            self.assertTrue(isinstance(message, basestring))

    def test_logging(self):
        message = gettextutils.Message('test ' + unichr(300), 'test')
        logger = logging.getLogger('whatever')
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s '
                                      '- %(user)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        params = {'user': unicode('test')}
        logger.info(message, extra=params)

    def test_get_localized_message(self):
        non_message = 'Non-translatable Message'
        en_message = 'A message in the default locale'
        es_translation = 'A message in Spanish'
        zh_translation = 'A message in Chinese'
        message = gettextutils.Message(en_message, 'test_domain')

        # In the Message class the translation ultimately occurs when the
        # message ID is resolved, and that is what we mock here
        def _mock_es(msg):
            return es_translation

        def _mock_zh(msg):
            return zh_translation

        def _mock_def(msg):
            return msg

        def _mock_gtm(domain, locale):
            if locale == 'es':
                return _mock_es
            if locale == 'zh':
                return _mock_zh
            return _mock_def

        _mock_gtm = staticmethod(_mock_gtm)

        self.stubs.Set(gettextutils.Message,
                       'get_translation_method', _mock_gtm)


        self.assertEqual(es_translation,
                         gettextutils.get_localized_message(message, 'es'))
        self.assertEqual(zh_translation,
                         gettextutils.get_localized_message(message, 'zh'))
        self.assertEqual(en_message,
                         gettextutils.get_localized_message(message, 'en'))
        self.assertEqual(en_message,
                         gettextutils.get_localized_message(message, 'XX'))
        self.assertEqual(en_message,
                         gettextutils.get_localized_message(message, None))
        self.assertEqual(non_message,
                         gettextutils.get_localized_message(non_message, 'A'))

    @mock.patch('gettext.translation')
    def test_get_localized_message_with_param(self, mock_translation):
        message_with_params = 'A message: %s'
        es_translation = 'A message: %s'
        param = 'A Message param'

        translations = {message_with_params: es_translation}
        translator = TestTranslations.translator(translations, 'es')
        mock_translation.side_effect = translator

        msg = gettextutils.Message(message_with_params, 'test_domain')
        msg = msg % param

        expected_translation = es_translation % param
        self._assert_translations(msg, 'es', expected_translation)

    @mock.patch('gettext.translation')
    def test_get_localized_message_with_message_param(self, mock_translation):
        message_with_params = 'A message with param: %s'
        es_translation = 'A message with param in Spanish: %s'
        message_param = 'A message param'
        es_param_translation = 'A message param in Spanish'

        translations = {message_with_params: es_translation,
                        message_param: es_param_translation}
        translator = TestTranslations.translator(translations, 'es')
        mock_translation.side_effect = translator

        msg = gettextutils.Message(message_with_params, 'test_domain')
        msg_param = gettextutils.Message(message_param, 'test_domain')
        msg = msg % msg_param

        expected_translation = es_translation % es_param_translation
        self._assert_translations(msg, 'es', expected_translation)

    @mock.patch('gettext.translation')
    def test_get_localized_message_with_message_params(self, mock_translation):
        message_with_params = 'A message with params: %s %s'
        es_translation = 'A message with params in Spanish: %s %s'
        message_param = 'A message param'
        es_param_translation = 'A message param in Spanish'
        another_message_param = 'Another message param'
        another_es_param_translation = 'Another message param in Spanish'

        translations = {message_with_params: es_translation,
                        message_param: es_param_translation,
                        another_message_param: another_es_param_translation}
        translator = TestTranslations.translator(translations, 'es')
        mock_translation.side_effect = translator

        msg = gettextutils.Message(message_with_params, 'test_domain')
        param_1 = gettextutils.Message(message_param, 'test_domain')
        param_2 = gettextutils.Message(another_message_param, 'test_domain')
        msg = msg % (param_1, param_2)

        expected_translation = es_translation % (es_param_translation,
                                                 another_es_param_translation)
        self._assert_translations(msg, 'es', expected_translation)

    @mock.patch('gettext.translation')
    def test_get_localized_message_with_named_params(self, mock_translation):
        message_with_params = 'A message with params: %(param)s'
        es_translation = 'A message with params in Spanish: %(param)s'
        message_param = 'A Message param'
        es_param_translation = 'A message param in Spanish'

        translations = {message_with_params: es_translation,
                        message_param: es_param_translation}
        translator = TestTranslations.translator(translations, 'es')
        mock_translation.side_effect = translator

        msg = gettextutils.Message(message_with_params, 'test_domain')
        msg_param = gettextutils.Message(message_param, 'test_domain')
        msg = msg % {'param': msg_param}

        expected_translation = es_translation % {'param': es_param_translation}
        self._assert_translations(msg, 'es', expected_translation)

    def _assert_translations(self, msg, locale, expected_translation):
        """Validates that the message translation in the given locale is as
        expected. For sanity, other locales are tested too and those should
        result in the same message being passed in.
        """
        self.assertEqual(unicode(msg),
                         gettextutils.get_localized_message(msg, 'en'))
        self.assertEqual(unicode(msg),
                         gettextutils.get_localized_message(msg, 'XX'))
        self.assertEqual(unicode(msg),
                         gettextutils.get_localized_message(msg, None))
        self.assertEqual(unicode(expected_translation),
                         gettextutils.get_localized_message(msg, locale))

    def test_get_available_languages(self):
        # All the available languages for which locale data is available
        def _mock_locale_identifiers():
            return ['zh', 'es', 'nl', 'fr']

        self.stubs.Set(localedata,
                       'list' if hasattr(localedata, 'list')
                       else 'locale_identifiers',
                       _mock_locale_identifiers)

        # Only the languages available for a specific translation domain
        def _mock_gettext_find(domain, localedir=None, languages=[], all=0):
            if domain == 'domain_1':
                return 'translation-file' if any(x in ['zh', 'es']
                                                 for x in languages) else None
            elif domain == 'domain_2':
                return 'translation-file' if any(x in ['fr']
                                                 for x in languages) else None
            return None
        self.stubs.Set(gettext, 'find', _mock_gettext_find)

        # en_US should always be available no matter the domain
        # and it should also always be the first element since order matters
        domain_1_languages = gettextutils.get_available_languages('domain_1')
        domain_2_languages = gettextutils.get_available_languages('domain_2')
        self.assertEquals('en_US', domain_1_languages[0])
        self.assertEquals('en_US', domain_2_languages[0])
        # Only the domain languages should be included after en_US
        self.assertEquals(3, len(domain_1_languages))
        self.assertIn('zh', domain_1_languages)
        self.assertIn('es', domain_1_languages)
        self.assertEquals(2, len(domain_2_languages))
        self.assertIn('fr', domain_2_languages)
        self.assertEquals(2, len(gettextutils._AVAILABLE_LANGUAGES))
        # Now test an unknown domain, only en_US should be included
        unknown_domain_languages = gettextutils.get_available_languages('huh')
        self.assertEquals(1, len(unknown_domain_languages))
        self.assertIn('en_US', unknown_domain_languages)


class MessageTestCase(test.BaseTestCase):
    """Unit tests for locale Message class."""

    def setUp(self):
        super(MessageTestCase, self).setUp()
        self.mox = self.useFixture(moxstubout.MoxStubout()).mox

    @staticmethod
    def _lazy_gettext(msg):
        message = gettextutils.Message(msg, 'oslo')
        return message

    def tearDown(self):
        # need to clean up stubs early since they interfere
        # with super class clean up operations
        self.mox.UnsetStubs()
        super(MessageTestCase, self).tearDown()

    def test_message_equal_to_string(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        self.assertEqual(result, msgid)

    def test_message_not_equal(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        self.assertNotEqual(result, "Other string %s" % msgid)

    def test_message_equal_with_param(self):
        msgid = "Some string with params: %s"
        params = (0, )

        message = msgid % params

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, message)

        result_str = '%s' % result
        self.assertEqual(result_str, message)

    def test_message_injects_nonetype(self):
        msgid = "Some string with param: %s"
        params = None

        message = msgid % params

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, message)

        result_str = '%s' % result
        self.assertIn('None', result_str)
        self.assertEqual(result_str, message)

    def test_message_iterate(self):
        msgid = "Some string with params: %s"
        params = 'blah'

        message = msgid % params

        result = self._lazy_gettext(msgid) % params

        # compare using iterators
        for (c1, c2) in zip(result, message):
            self.assertEqual(c1, c2)

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

    def test_regex_find_named_parameters_no_space(self):
        msgid = ("Request: %(method)s http://%(server)s:"
                 "%(port)s%(url)s with headers %(headers)s")
        params = {'method': 'POST',
                  'server': 'test1',
                  'port': 1234,
                  'url': 'test2',
                  'headers': {'h1': 'val1'}}

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, msgid % params)

    def test_regex_dict_is_parameter(self):
        msgid = ("Test that we can inject a dictionary %s")
        params = {'description': 'test1'}

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, msgid % params)

    def test_message_equal_with_dec_param(self):
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

    def test_message_equal_with_extra_params(self):
        msgid = "Some string with params: %(param1)s %(param2)s"
        params = {'param1': 'test',
                  'param2': 'test2',
                  'param3': 'notinstring'}

        result = self._lazy_gettext(msgid) % params

        self.assertEqual(result, msgid % params)

    def test_message_object_param_copied(self):
        """Verify that injected parameters get copied."""
        some_obj = SomeObject()
        some_obj.tag = 'stub_object'
        msgid = "Found object: %(some_obj)s"

        result = self._lazy_gettext(msgid) % {'some_obj': some_obj}

        old_some_obj = copy.copy(some_obj)
        some_obj.tag = 'switched_tag'

        self.assertEqual(result, msgid % {'some_obj': old_some_obj})

    def test_interpolation_with_missing_param(self):
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

    def test_get_slice(self):
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        expected = msgid[2:-1]
        result = result[2:-1]

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

    def _get_testmsg_inner_params(self):
        return {'params': {'test1': 'blah1',
                           'test2': 'blah2',
                           'test3': SomeObject()},
                'domain': 'test_domain',
                'locale': 'en_US',
                '_left_extra_msg': 'Extra. ',
                '_right_extra_msg': '. More Extra.'}

    def _get_full_test_message(self):
        msgid = "Some msgid string: %(test1)s %(test2)s %(test3)s"
        message = self._lazy_gettext(msgid)
        message.domain = 'test_domain'
        message = message % {'test1': 'blah1',
                             'test2': 'blah2',
                             'test3': SomeObject()}
        message = message.translate_into('en_US')
        message = message.__add__('Extra .')
        message = message.__radd__('. More Extra.')
        return copy.deepcopy(message)

    def test_message_copyable(self):
        message = self._get_full_test_message()
        copied_msg = copy.copy(message)

        self.assertIsNot(message, copied_msg)

        for k in message.__getstate__():
            self.assertEqual(getattr(message, k),
                             getattr(copied_msg, k))

        self.assertEqual(message, copied_msg)

    def test_add_returns_copy(self):
        msgid = "Some msgid string: %(test1)s %(test2)s"
        message = self._lazy_gettext(msgid)
        m1 = '10 ' + message + ' 10'
        m2 = '20 ' + message + ' 20'

        self.assertIsNot(message, m1)
        self.assertIsNot(message, m2)
        self.assertIsNot(m1, m2)
        self.assertEqual(m1, '10 %s 10' % msgid)
        self.assertEqual(m2, '20 %s 20' % msgid)

    def test_mod_returns_copy(self):
        msgid = "Some msgid string: %(test1)s %(test2)s"
        message = self._lazy_gettext(msgid)
        m1 = message % {'test1': 'foo', 'test2': 'bar'}
        m2 = message % {'test1': 'foo2', 'test2': 'bar2'}

        self.assertIsNot(message, m1)
        self.assertIsNot(message, m2)
        self.assertIsNot(m1, m2)
        self.assertEqual(m1, msgid % {'test1': 'foo', 'test2': 'bar'})
        self.assertEqual(m2, msgid % {'test1': 'foo2', 'test2': 'bar2'})

    def test_comparator_operators(self):
        """Verify Message comparison is equivalent to string comparision."""
        m1 = self._get_full_test_message()
        m2 = copy.deepcopy(m1)
        m3 = "1" + m1

        # m1 and m2 are equal
        self.assertEqual(m1 >= m2, str(m1) >= str(m2))
        self.assertEqual(m1 <= m2, str(m1) <= str(m2))
        self.assertEqual(m2 >= m1, str(m2) >= str(m1))
        self.assertEqual(m2 <= m1, str(m2) <= str(m1))

        # m1 is greater than m3
        self.assertEqual(m1 >= m3, str(m1) >= str(m3))
        self.assertEqual(m1 > m3, str(m1) > str(m3))

        # m3 is not greater than m1
        self.assertEqual(m3 >= m1, str(m3) >= str(m1))
        self.assertEqual(m3 > m1, str(m3) > str(m1))

        # m3 is less than m1
        self.assertEqual(m3 <= m1, str(m3) <= str(m1))
        self.assertEqual(m3 < m1, str(m3) < str(m1))

        # m3 is not less than m1
        self.assertEqual(m1 <= m3, str(m1) <= str(m3))
        self.assertEqual(m1 < m3, str(m1) < str(m3))

    def test_mul_operator(self):
        message = self._get_full_test_message()
        message_str = str(message)

        self.assertEqual(message * 10, message_str * 10)
        self.assertEqual(message * 20, message_str * 20)
        self.assertEqual(10 * message, 10 * message_str)
        self.assertEqual(20 * message, 20 * message_str)

    def test_to_unicode(self):
        message = self._get_full_test_message()
        message_str = six.text_type(message)

        self.assertEqual(message, message_str)
        self.assertTrue(isinstance(message_str, six.text_type))

    def test_upper(self):
        # test an otherwise uncovered __getattribute__ path
        msgid = "Some msgid string"
        result = self._lazy_gettext(msgid)

        self.assertEqual(msgid.upper(), result.upper())


class LocaleHandlerTestCase(test.BaseTestCase):

    def setUp(self):
        super(LocaleHandlerTestCase, self).setUp()
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs

        def _message_with_domain(msg):
            message = gettextutils.Message(msg, 'oslo')
            return message

        self._lazy_gettext = _message_with_domain
        self.buffer_handler = logging.handlers.BufferingHandler(40)
        self.locale_handler = gettextutils.LocaleHandler(
            'zh_CN', self.buffer_handler)
        self.logger = logging.getLogger('localehander_logger')
        self.logger.propogate = False
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.locale_handler)

    def test_emit_message(self):
        msgid = 'Some logrecord message.'
        message = self._lazy_gettext(msgid)
        self.emit_called = False

        def emit(record):
            self.assertEqual(record.msg.locale, 'zh_CN')
            self.assertEqual(record.msg, msgid)
            self.assertTrue(isinstance(record.msg,
                                       gettextutils.Message))
            self.emit_called = True
        self.stubs.Set(self.buffer_handler, 'emit', emit)

        self.logger.info(message)

        self.assertTrue(self.emit_called)

    def test_emit_nonmessage(self):
        msgid = 'Some logrecord message.'
        self.emit_called = False

        def emit(record):
            self.assertEqual(record.msg, msgid)
            self.assertFalse(isinstance(record.msg,
                                        gettextutils.Message))
            self.emit_called = True
        self.stubs.Set(self.buffer_handler, 'emit', emit)

        self.logger.info(msgid)

        self.assertTrue(self.emit_called)


class TestTranslations(gettext.GNUTranslations):
    """A test GNUTranslations class that takes a map of msg -> translations."""

    def __init__(self, translations):
        self.translations = translations

    def ugettext(self, msgid):
        return self.translations.get(msgid, msgid)

    @staticmethod
    def translator(translation_map, language):
        """Returns a mock gettext.translation function that uses
        TestTranslation to translate in the given locale.
        """
        def _translation(domain, localedir=None,
                         languages=None, fallback=None):
            if languages and language in languages:
                return TestTranslations(translation_map)
            return gettext.NullTranslations()
        return _translation


class SomeObject(object):

    def __init__(self, tag='default'):
        self.tag = tag

    def __str__(self):
        return self.tag

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state):
        for (k, v) in state.items():
            setattr(self, k, v)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.tag == other.tag
        return False
