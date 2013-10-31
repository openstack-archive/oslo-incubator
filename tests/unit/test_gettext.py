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

import gettext
import logging.handlers

from babel import localedata
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
        self.assertEqual('en_US', domain_1_languages[0])
        self.assertEqual('en_US', domain_2_languages[0])
        # Only the domain languages should be included after en_US
        self.assertEqual(3, len(domain_1_languages))
        self.assertIn('zh', domain_1_languages)
        self.assertIn('es', domain_1_languages)
        self.assertEqual(2, len(domain_2_languages))
        self.assertIn('fr', domain_2_languages)
        self.assertEqual(2, len(gettextutils._AVAILABLE_LANGUAGES))
        # Now test an unknown domain, only en_US should be included
        unknown_domain_languages = gettextutils.get_available_languages('huh')
        self.assertEqual(1, len(unknown_domain_languages))
        self.assertIn('en_US', unknown_domain_languages)


class MessageTestCase(test.BaseTestCase):
    """Unit tests for locale Message class."""

    @staticmethod
    def message(msg):
        return gettextutils.Message(msg, 'oslo')

    def test_message_is_unicode(self):
        message = self.message('some %s') % 'message'
        self.assertTrue(isinstance(message, six.text_type))

    def test_translate_returns_unicode(self):
        message = self.message('some %s') % 'message'
        self.assertTrue(isinstance(message.translate(), six.text_type))

    def test_mod_with_named_parameters(self):
        msgid = ("%(description)s\nCommand: %(cmd)s\n"
                 "Exit code: %(exit_code)s\nStdout: %(stdout)r\n"
                 "Stderr: %(stderr)r %%(something)s")
        params = {'description': 'test1',
                  'cmd': 'test2',
                  'exit_code': 'test3',
                  'stdout': 'test4',
                  'stderr': 'test5',
                  'something': 'trimmed'}

        result = self.message(msgid) % params

        expected = msgid % params
        self.assertEqual(result, expected)
        self.assertEqual(result.translate(), expected)

    def test_mod_with_named_parameters_no_space(self):
        msgid = ("Request: %(method)s http://%(server)s:"
                 "%(port)s%(url)s with headers %(headers)s")
        params = {'method': 'POST',
                  'server': 'test1',
                  'port': 1234,
                  'url': 'test2',
                  'headers': {'h1': 'val1'}}

        result = self.message(msgid) % params

        expected = msgid % params
        self.assertEqual(result, expected)
        self.assertEqual(result.translate(), expected)

    def test_mod_with_dict_parameter(self):
        msgid = ("Test that we can inject a dictionary %s")
        params = {'description': 'test1'}

        result = self.message(msgid) % params

        expected = msgid % params
        self.assertEqual(result, expected)
        self.assertEqual(result.translate(), expected)

    def test_mod_with_integer_parameters(self):
        msgid = "Some string with params: %d"
        params = [0, 1, 10, 24124]

        messages = []
        results = []
        for param in params:
            messages.append(msgid % param)
            results.append(self.message(msgid) % param)

        for message, result in zip(messages, results):
            self.assertEqual(type(result), gettextutils.Message)
            self.assertEqual(result.translate(), message)

            # simulate writing out as string
            result_str = '%s' % result.translate()
            self.assertEqual(result_str, message)
            self.assertEqual(result, message)

    def test_mod_copies_parameters(self):
        msgid = "Found object: %(current_value)s"
        changing_dict = {'current_value': 1}
        # A message created with some params
        result = self.message(msgid) % changing_dict
        # The parameters may change
        changing_dict['current_value'] = 2
        # Even if the param changes when the message is
        # translated it should use the original param
        self.assertEqual(result.translate(), 'Found object: 1')

    def test_mod_returns_a_copy(self):
        msgid = "Some msgid string: %(test1)s %(test2)s"
        message = self.message(msgid)
        m1 = message % {'test1': 'foo', 'test2': 'bar'}
        m2 = message % {'test1': 'foo2', 'test2': 'bar2'}

        self.assertIsNot(message, m1)
        self.assertIsNot(message, m2)
        self.assertEqual(m1.translate(),
                         msgid % {'test1': 'foo', 'test2': 'bar'})
        self.assertEqual(m2.translate(),
                         msgid % {'test1': 'foo2', 'test2': 'bar2'})

    def test_mod_with_none_parameter(self):
        msgid = "Some string with params: %s"
        message = self.message(msgid) % None
        self.assertEqual(msgid % None, message)
        self.assertEqual(msgid % None, message.translate())

    def test_mod_with_missing_parameters(self):
        msgid = "Some string with params: %s %s"
        test_me = lambda: self.message(msgid) % 'just one'
        # Just like with strings missing parameters raise TypeError
        self.assertRaises(TypeError, test_me)

    def test_mod_with_extra_parameters(self):
        msgid = "Some string with params: %(param1)s %(param2)s"
        params = {'param1': 'test',
                  'param2': 'test2',
                  'param3': 'notinstring'}

        result = self.message(msgid) % params

        expected = msgid % params
        self.assertEqual(result, expected)
        self.assertEqual(result.translate(), expected)

    def test_mod_with_missing_named_parameters(self):
        msgid = ("Some string with params: %(param1)s %(param2)s"
                 " and a missing one %(missing)s")
        params = {'param1': 'test',
                  'param2': 'test2'}

        test_me = lambda: self.message(msgid) % params
        # Just like with strings missing named parameters raise KeyError
        self.assertRaises(KeyError, test_me)

    @mock.patch('gettext.translation')
    def test_translate(self, mock_translation):
        en_message = 'A message in the default locale'
        es_translation = 'A message in Spanish'
        message = gettextutils.Message(en_message, 'test_domain')

        es_translations = {en_message: es_translation}
        translations_map = {'es': es_translations}
        translator = TestTranslations.translator(translations_map)
        mock_translation.side_effect = translator

        self.assertEqual(es_translation, message.translate('es'))

    @mock.patch('gettext.translation')
    def test_translate_message_from_unicoded_object(self, mock_translation):
        en_message = 'A message in the default locale'
        es_translation = 'A message in Spanish'
        message = gettextutils.Message(en_message, 'test_domain')
        es_translations = {en_message: es_translation}
        translations_map = {'es': es_translations}
        translator = TestTranslations.translator(translations_map)
        mock_translation.side_effect = translator

        # Here we are not testing the Message object directly but the result
        # of unicoding() an object whose unicode representation is a Message
        obj = SomeObject(message)
        unicoded_obj = six.text_type(obj)

        self.assertEqual(es_translation, unicoded_obj.translate('es'))

    @mock.patch('gettext.translation')
    def test_translate_multiple_languages(self, mock_translation):
        en_message = 'A message in the default locale'
        es_translation = 'A message in Spanish'
        zh_translation = 'A message in Chinese'
        message = gettextutils.Message(en_message, 'test_domain')

        es_translations = {en_message: es_translation}
        zh_translations = {en_message: zh_translation}
        translations_map = {'es': es_translations,
                            'zh': zh_translations}
        translator = TestTranslations.translator(translations_map)
        mock_translation.side_effect = translator

        self.assertEqual(es_translation, message.translate('es'))
        self.assertEqual(zh_translation, message.translate('zh'))
        self.assertEqual(en_message, message.translate(None))
        self.assertEqual(en_message, message.translate('en'))
        self.assertEqual(en_message, message.translate('XX'))

    @mock.patch('gettext.translation')
    def test_translate_message_with_param(self, mock_translation):
        message_with_params = 'A message: %s'
        es_translation = 'A message in Spanish: %s'
        param = 'A Message param'

        translations = {message_with_params: es_translation}
        translator = TestTranslations.translator({'es': translations})
        mock_translation.side_effect = translator

        msg = gettextutils.Message(message_with_params, 'test_domain')
        msg = msg % param

        default_translation = message_with_params % param
        expected_translation = es_translation % param
        self.assertEqual(expected_translation, msg.translate('es'))
        self.assertEqual(default_translation, msg.translate('XX'))

    @mock.patch('gettext.translation')
    def test_translate_message_with_param_from_unicoded_obj(self,
                                                            mock_translation):
        message_with_params = 'A message: %s'
        es_translation = 'A message in Spanish: %s'
        param = 'A Message param'

        translations = {message_with_params: es_translation}
        translator = TestTranslations.translator({'es': translations})
        mock_translation.side_effect = translator

        msg = gettextutils.Message(message_with_params, 'test_domain')
        msg = msg % param

        default_translation = message_with_params % param
        expected_translation = es_translation % param

        obj = SomeObject(msg)
        unicoded_obj = six.text_type(obj)

        self.assertEqual(expected_translation, unicoded_obj.translate('es'))
        self.assertEqual(default_translation, unicoded_obj.translate('XX'))

    @mock.patch('gettext.translation')
    def test_translate_message_with_message_parameter(self, mock_translation):
        message_with_params = 'A message with param: %s'
        es_translation = 'A message with param in Spanish: %s'
        message_param = 'A message param'
        es_param_translation = 'A message param in Spanish'

        translations = {message_with_params: es_translation,
                        message_param: es_param_translation}
        translator = TestTranslations.translator({'es': translations})
        mock_translation.side_effect = translator

        msg = gettextutils.Message(message_with_params, 'test_domain')
        msg_param = gettextutils.Message(message_param, 'test_domain')
        msg = msg % msg_param

        default_translation = message_with_params % message_param
        expected_translation = es_translation % es_param_translation
        self.assertEqual(expected_translation, msg.translate('es'))
        self.assertEqual(default_translation, msg.translate('XX'))

    @mock.patch('gettext.translation')
    def test_translate_message_with_message_parameters(self, mock_translation):
        message_with_params = 'A message with params: %s %s'
        es_translation = 'A message with params in Spanish: %s %s'
        message_param = 'A message param'
        es_param_translation = 'A message param in Spanish'
        another_message_param = 'Another message param'
        another_es_param_translation = 'Another message param in Spanish'

        translations = {message_with_params: es_translation,
                        message_param: es_param_translation,
                        another_message_param: another_es_param_translation}
        translator = TestTranslations.translator({'es': translations})
        mock_translation.side_effect = translator

        msg = gettextutils.Message(message_with_params, 'test_domain')
        param_1 = gettextutils.Message(message_param, 'test_domain')
        param_2 = gettextutils.Message(another_message_param, 'test_domain')
        msg = msg % (param_1, param_2)

        default_translation = message_with_params % (message_param,
                                                     another_message_param)
        expected_translation = es_translation % (es_param_translation,
                                                 another_es_param_translation)
        self.assertEqual(expected_translation, msg.translate('es'))
        self.assertEqual(default_translation, msg.translate('XX'))

    @mock.patch('gettext.translation')
    def test_translate_message_with_named_parameters(self, mock_translation):
        message_with_params = 'A message with params: %(param)s'
        es_translation = 'A message with params in Spanish: %(param)s'
        message_param = 'A Message param'
        es_param_translation = 'A message param in Spanish'

        translations = {message_with_params: es_translation,
                        message_param: es_param_translation}
        translator = TestTranslations.translator({'es': translations})
        mock_translation.side_effect = translator

        msg = gettextutils.Message(message_with_params, 'test_domain')
        msg_param = gettextutils.Message(message_param, 'test_domain')
        msg = msg % {'param': msg_param}

        default_translation = message_with_params % {'param': message_param}
        expected_translation = es_translation % {'param': es_param_translation}
        self.assertEqual(expected_translation, msg.translate('es'))
        self.assertEqual(default_translation, msg.translate('XX'))


class LocaleHandlerTestCase(test.BaseTestCase):

    def setUp(self):
        super(LocaleHandlerTestCase, self).setUp()
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs

        def _message_with_domain(msg):
            return gettextutils.Message(msg, 'oslo')

        self._ = _message_with_domain
        self.buffer_handler = logging.handlers.BufferingHandler(40)
        self.locale_handler = gettextutils.LocaleHandler(
            'zh_CN', self.buffer_handler)
        self.logger = logging.getLogger('localehander_logger')
        self.logger.propogate = False
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.locale_handler)

    def test_emit_message(self):
        msgid = 'Some logrecord message.'
        message = gettextutils.Message(msgid, 'test')
        self.emit_called = False

        def emit(record):
            self.assertEqual(record.msg.translate('zh_CN'), msgid)
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
    def translator(locales_map):
        """Returns a mock gettext.translation function that uses
        individual TestTranslations to translate in the given locales.

        :param locales_map: A map from locale name to a translations mapg.
                            {
                             'es': {'Hi': 'Hola", 'Bye': 'Adios'},
                             'zh': {'Hi': 'Ni Hao', 'Bye': 'Zaijian'}
                            }
        """
        def _translation(domain, localedir=None,
                         languages=None, fallback=None):
            if languages:
                language = languages.pop()
                if language in locales_map:
                    return TestTranslations(locales_map[language])
            return gettext.NullTranslations()
        return _translation


class SomeObject(object):

    def __init__(self, message):
        self.message = message

    def __unicode__(self):
        return self.message
