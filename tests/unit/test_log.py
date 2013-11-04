# Copyright (c) 2011 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.

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

import logging
import os
import sys

import mock
from oslo.config import cfg
import six

from openstack.common import context
from openstack.common import fileutils
from openstack.common.fixture import config
from openstack.common.fixture import moxstubout
from openstack.common import gettextutils
from openstack.common import jsonutils
from openstack.common import log
from openstack.common import log_handler
from openstack.common.notifier import api as notifier
from openstack.common import test


def _fake_context():
    return context.RequestContext(1, 1)


class CommonLoggerTestsMixIn(object):
    """These tests are shared between LoggerTestCase and
    LazyLoggerTestCase.
    """

    def setUp(self):
        super(CommonLoggerTestsMixIn, self).setUp()
        self.config = self.useFixture(config.Config()).config

        # common context has different fields to the defaults in log.py
        self.config(logging_context_format_string='%(asctime)s %(levelname)s '
                                                  '%(name)s [%(request_id)s '
                                                  '%(user)s %(tenant)s] '
                                                  '%(message)s')
        self.log = None

    def test_handlers_have_context_formatter(self):
        formatters = []
        for h in self.log.logger.handlers:
            f = h.formatter
            if isinstance(f, log.ContextFormatter):
                formatters.append(f)
        self.assertTrue(formatters)
        self.assertEqual(len(formatters), len(self.log.logger.handlers))

    def test_handles_context_kwarg(self):
        self.log.info("foo", context=_fake_context())
        self.assertTrue(True)  # didn't raise exception

    def test_audit_handles_context_arg(self):
        self.log.audit("foo", context=_fake_context())
        self.assertTrue(True)  # didn't raise exception

    def test_will_be_verbose_if_verbose_flag_set(self):
        self.config(verbose=True)
        log.setup("test_is_verbose")
        logger = logging.getLogger("test_is_verbose")
        self.assertEqual(logging.INFO, logger.getEffectiveLevel())

    def test_will_be_debug_if_debug_flag_set(self):
        self.config(debug=True)
        log.setup("test_is_debug")
        logger = logging.getLogger("test_is_debug")
        self.assertEqual(logging.DEBUG, logger.getEffectiveLevel())

    def test_will_not_be_verbose_if_verbose_flag_not_set(self):
        self.config(verbose=False)
        log.setup("test_is_not_verbose")
        logger = logging.getLogger("test_is_not_verbose")
        self.assertEqual(logging.WARNING, logger.getEffectiveLevel())

    def test_no_logging_via_module(self):
        for func in ('critical', 'error', 'exception', 'warning', 'warn',
                     'info', 'debug', 'log', 'audit'):
            self.assertRaises(AttributeError, getattr, log, func)


class LoggerTestCase(CommonLoggerTestsMixIn, test.BaseTestCase):
    def setUp(self):
        super(LoggerTestCase, self).setUp()
        self.log = log.getLogger()


class LazyLoggerTestCase(CommonLoggerTestsMixIn, test.BaseTestCase):
    def setUp(self):
        super(LazyLoggerTestCase, self).setUp()
        self.log = log.getLazyLogger()


class LogHandlerTestCase(test.BaseTestCase):

    def setUp(self):
        super(LogHandlerTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config

    def test_log_path_logdir(self):
        self.config(log_dir='/some/path', log_file=None)
        self.assertEqual(log._get_log_file_path(binary='foo-bar'),
                         '/some/path/foo-bar.log')

    def test_log_path_logfile(self):
        self.config(log_file='/some/path/foo-bar.log')
        self.assertEqual(log._get_log_file_path(binary='foo-bar'),
                         '/some/path/foo-bar.log')

    def test_log_path_none(self):
        self.config(log_dir=None, log_file=None)
        self.assertTrue(log._get_log_file_path(binary='foo-bar') is None)

    def test_log_path_logfile_overrides_logdir(self):
        self.config(log_dir='/some/other/path',
                    log_file='/some/path/foo-bar.log')
        self.assertEqual(log._get_log_file_path(binary='foo-bar'),
                         '/some/path/foo-bar.log')


class PublishErrorsHandlerTestCase(test.BaseTestCase):
    """Tests for log.PublishErrorsHandler"""
    def setUp(self):
        super(PublishErrorsHandlerTestCase, self).setUp()
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs
        self.config = self.useFixture(config.Config()).config
        self.publiserrorshandler = log_handler.\
            PublishErrorsHandler(logging.ERROR)

    def test_emit_cfg_log_notifier_in_notifier_drivers(self):
        self.config(notification_driver=[
            'openstack.common.notifier.rabbit_notifier',
            'openstack.common.notifier.log_notifier'])
        self.stub_flg = True

        def fake_notifier(*args, **kwargs):
            self.stub_flg = False

        self.stubs.Set(notifier, 'notify', fake_notifier)
        logrecord = logging.LogRecord('name', 'WARN', '/tmp', 1,
                                      'Message', None, None)
        self.publiserrorshandler.emit(logrecord)
        self.assertTrue(self.stub_flg)


class LogLevelTestCase(test.BaseTestCase):
    def setUp(self):
        super(LogLevelTestCase, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        levels = self.CONF.default_log_levels
        levels.append("nova-test=AUDIT")
        self.config = self.useFixture(config.Config()).config
        self.config(default_log_levels=levels,
                    verbose=True)
        log.setup('testing')
        self.log = log.getLogger('nova-test')

    def test_has_level_from_flags(self):
        self.assertEqual(logging.AUDIT, self.log.logger.getEffectiveLevel())

    def test_child_log_has_level_of_parent_flag(self):
        l = log.getLogger('nova-test.foo')
        self.assertEqual(logging.AUDIT, l.logger.getEffectiveLevel())


class JSONFormatterTestCase(test.BaseTestCase):
    def setUp(self):
        super(JSONFormatterTestCase, self).setUp()
        self.log = log.getLogger('test-json')
        self.stream = six.StringIO()
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(log.JSONFormatter())
        self.log.logger.addHandler(handler)
        self.log.logger.setLevel(logging.DEBUG)

    def test_json(self):
        test_msg = 'This is a %(test)s line'
        test_data = {'test': 'log'}
        self.log.debug(test_msg, test_data)

        data = jsonutils.loads(self.stream.getvalue())
        self.assertTrue(data)
        self.assertTrue('extra' in data)
        self.assertEqual('test-json', data['name'])

        self.assertEqual(test_msg % test_data, data['message'])
        self.assertEqual(test_msg, data['msg'])
        self.assertEqual(test_data, data['args'])

        self.assertEqual('test_log.py', data['filename'])
        self.assertEqual('test_json', data['funcname'])

        self.assertEqual('DEBUG', data['levelname'])
        self.assertEqual(logging.DEBUG, data['levelno'])
        self.assertFalse(data['traceback'])

    def test_json_exception(self):
        test_msg = 'This is %s'
        test_data = 'exceptional'
        try:
            raise Exception('This is exceptional')
        except Exception:
            self.log.exception(test_msg, test_data)

        data = jsonutils.loads(self.stream.getvalue())
        self.assertTrue(data)
        self.assertTrue('extra' in data)
        self.assertEqual('test-json', data['name'])

        self.assertEqual(test_msg % test_data, data['message'])
        self.assertEqual(test_msg, data['msg'])
        self.assertEqual([test_data], data['args'])

        self.assertEqual('ERROR', data['levelname'])
        self.assertEqual(logging.ERROR, data['levelno'])
        self.assertTrue(data['traceback'])


class ContextFormatterTestCase(test.BaseTestCase):
    def setUp(self):
        super(ContextFormatterTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config
        self.config(logging_context_format_string="HAS CONTEXT "
                                                  "[%(request_id)s]: "
                                                  "%(message)s",
                    logging_default_format_string="NOCTXT: %(message)s",
                    logging_debug_format_suffix="--DBG")
        self.log = log.getLogger()
        self.stream = six.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(log.ContextFormatter())
        self.log.logger.addHandler(self.handler)
        self.addCleanup(self.log.logger.removeHandler, self.handler)
        self.level = self.log.logger.getEffectiveLevel()
        self.log.logger.setLevel(logging.DEBUG)
        self.addCleanup(self.log.logger.setLevel, self.level)

    def test_uncontextualized_log(self):
        self.log.info("foo")
        self.assertEqual("NOCTXT: foo\n", self.stream.getvalue())

    def test_contextualized_log(self):
        ctxt = _fake_context()
        self.log.info("bar", context=ctxt)
        expected = "HAS CONTEXT [%s]: bar\n" % ctxt.request_id
        self.assertEqual(expected, self.stream.getvalue())

    def test_debugging_log(self):
        self.log.debug("baz")
        self.assertEqual("NOCTXT: baz --DBG\n", self.stream.getvalue())

    def test_message_logging(self):
        # NOTE(luisg): Logging message objects with unicode objects
        # may cause trouble by the logging mechanism trying to coerce
        # the Message object, with a wrong encoding. This test case
        # tests that problem does not occur.
        ctxt = _fake_context()
        ctxt.request_id = six.text_type('99')
        message = gettextutils.Message('test ' + unichr(128), 'test')
        self.log.info(message, context=ctxt)
        expected = "HAS CONTEXT [%s]: %s\n" % (ctxt.request_id,
                                               six.text_type(message))
        self.assertEqual(expected, self.stream.getvalue())


class ExceptionLoggingTestCase(test.BaseTestCase):
    """Test that Exceptions are logged."""

    def test_excepthook_logs_exception(self):
        product_name = 'somename'
        exc_log = log.getLogger(product_name)

        stream = six.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(log.ContextFormatter())
        exc_log.logger.addHandler(handler)
        self.addCleanup(exc_log.logger.removeHandler, handler)
        excepthook = log._create_logging_excepthook(product_name)

        try:
            raise Exception('Some error happened')
        except Exception:
            excepthook(*sys.exc_info())

        expected_string = "CRITICAL somename [-] Some error happened"
        self.assertTrue(expected_string in stream.getvalue(),
                        msg="Exception is not logged")

    def test_excepthook_installed(self):
        log.setup("test_excepthook_installed")
        self.assertTrue(sys.excepthook != sys.__excepthook__)


class FancyRecordTestCase(test.BaseTestCase):
    """Test how we handle fancy record keys that are not in the
    base python logging.
    """

    def setUp(self):
        super(FancyRecordTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config
        # NOTE(sdague): use the different formatters to demonstrate format
        # string with valid fancy keys and without. Slightly hacky, but given
        # the way log objects layer up seemed to be most concise approach
        self.config(logging_context_format_string="%(color)s "
                                                  "[%(request_id)s]: "
                                                  "%(instance)s"
                                                  "%(message)s",
                    logging_default_format_string="%(missing)s: %(message)s")
        self.stream = six.StringIO()

        self.colorhandler = log.ColorHandler(self.stream)
        self.colorhandler.setFormatter(log.ContextFormatter())

        self.colorlog = log.getLogger()
        self.colorlog.logger.addHandler(self.colorhandler)
        self.level = self.colorlog.logger.getEffectiveLevel()
        self.colorlog.logger.setLevel(logging.DEBUG)

    def test_unsupported_key_in_log_msg(self):
        # NOTE(sdague): exception logging bypasses the main stream
        # and goes to stderr. Suggests on a better way to do this are
        # welcomed.
        error = sys.stderr
        sys.stderr = six.StringIO()

        self.colorlog.info("foo")
        self.assertNotEqual(sys.stderr.getvalue().find("KeyError: 'missing'"),
                            -1)

        sys.stderr = error

    def _validate_keys(self, ctxt, keyed_log_string):
        infocolor = '\033[00;36m'
        warncolor = '\033[01;33m'
        infoexpected = "%s %s info\n" % (infocolor, keyed_log_string)
        warnexpected = "%s %s warn\n" % (warncolor, keyed_log_string)

        self.colorlog.info("info", context=ctxt)
        self.assertEqual(infoexpected, self.stream.getvalue())

        self.colorlog.warn("warn", context=ctxt)
        self.assertEqual(infoexpected + warnexpected, self.stream.getvalue())

    def test_fancy_key_in_log_msg(self):
        ctxt = _fake_context()
        self._validate_keys(ctxt, '[%s]:' % ctxt.request_id)

    def test_instance_key_in_log_msg(self):
        ctxt = _fake_context()
        ctxt.instance_uuid = '1234'
        self._validate_keys(ctxt, ('[%s]: [instance: %s]' %
                                   (ctxt.request_id, ctxt.instance_uuid)))


class SetDefaultsTestCase(test.BaseTestCase):
    class TestConfigOpts(cfg.ConfigOpts):
        def __call__(self, args=None):
            return cfg.ConfigOpts.__call__(self,
                                           args=args,
                                           prog='test',
                                           version='1.0',
                                           usage='%(prog)s FOO BAR',
                                           default_config_files=[])

    def setUp(self):
        super(SetDefaultsTestCase, self).setUp()
        self.conf = self.TestConfigOpts()
        self.conf.register_opts(log.log_opts)

    def test_default_to_none(self):
        log.set_defaults(logging_context_format_string=None)
        self.conf([])
        self.assertEqual(self.conf.logging_context_format_string, None)

    def test_change_default(self):
        my_default = '%(asctime)s %(levelname)s %(name)s [%(request_id)s '\
                     '%(user_id)s %(project)s] %(instance)s'\
                     '%(message)s'
        log.set_defaults(logging_context_format_string=my_default)
        self.conf([])
        self.assertEqual(self.conf.logging_context_format_string, my_default)


class LogConfigOptsTestCase(test.BaseTestCase):

    def setUp(self):
        super(LogConfigOptsTestCase, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf

    def test_print_help(self):
        f = six.StringIO()
        self.CONF([])
        self.CONF.print_help(file=f)
        self.assertTrue('debug' in f.getvalue())
        self.assertTrue('verbose' in f.getvalue())
        self.assertTrue('log-config' in f.getvalue())
        self.assertTrue('log-format' in f.getvalue())

    def test_debug_verbose(self):
        self.CONF(['--debug', '--verbose'])

        self.assertEqual(self.CONF.debug, True)
        self.assertEqual(self.CONF.verbose, True)

    def test_logging_opts(self):
        self.CONF([])

        self.assertTrue(self.CONF.log_config_append is None)
        self.assertTrue(self.CONF.log_file is None)
        self.assertTrue(self.CONF.log_dir is None)
        self.assertTrue(self.CONF.log_format is None)

        self.assertEqual(self.CONF.log_date_format,
                         log._DEFAULT_LOG_DATE_FORMAT)

        self.assertEqual(self.CONF.use_syslog, False)

    def test_log_file(self):
        log_file = '/some/path/foo-bar.log'
        self.CONF(['--log-file', log_file])
        self.assertEqual(self.CONF.log_file, log_file)

    def test_logfile_deprecated(self):
        logfile = '/some/other/path/foo-bar.log'
        self.CONF(['--logfile', logfile])
        self.assertEqual(self.CONF.log_file, logfile)

    def test_log_dir(self):
        log_dir = '/some/path/'
        self.CONF(['--log-dir', log_dir])
        self.assertEqual(self.CONF.log_dir, log_dir)

    def test_logdir_deprecated(self):
        logdir = '/some/other/path/'
        self.CONF(['--logdir', logdir])
        self.assertEqual(self.CONF.log_dir, logdir)

    def test_log_format_overrides_formatter(self):
        self.CONF(['--log-format', '[Any format]'])
        log._setup_logging_from_conf()
        logger = log._loggers[None].logger
        for handler in logger.handlers:
            formatter = handler.formatter
            self.assertTrue(isinstance(formatter, logging.Formatter))

    def test_default_formatter(self):
        log._setup_logging_from_conf()
        logger = log._loggers[None].logger
        for handler in logger.handlers:
            formatter = handler.formatter
            self.assertTrue(isinstance(formatter, log.ContextFormatter))


class LogConfigTestCase(test.BaseTestCase):

    minimal_config = """[loggers]
keys=root

[formatters]
keys=

[handlers]
keys=

[logger_root]
handlers=
"""

    def setUp(self):
        super(LogConfigTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config
        self.log_config_append = \
            fileutils.write_to_tempfile(content=self.minimal_config,
                                        prefix='logging',
                                        suffix='.conf'
                                        )

    def test_log_config_append_ok(self):
        self.config(log_config_append=self.log_config_append)
        log.setup('test_log_config_append')

    def test_log_config_append_not_exist(self):
        os.remove(self.log_config_append)
        self.config(log_config_append=self.log_config_append)
        self.assertRaises(log.LogConfigError, log.setup,
                          'test_log_config_append')

    def test_log_config_append_invalid(self):
        self.log_config_append = \
            fileutils.write_to_tempfile(content=self.minimal_config[5:],
                                        prefix='logging',
                                        suffix='.conf'
                                        )
        self.config(log_config_append=self.log_config_append)
        self.assertRaises(log.LogConfigError, log.setup,
                          'test_log_config_append')

    def test_log_config_append_unreadable(self):
        os.chmod(self.log_config_append, 0)
        self.config(log_config_append=self.log_config_append)
        self.assertRaises(log.LogConfigError, log.setup,
                          'test_log_config_append')

    def test_log_config_append_disable_existing_loggers(self):
        self.config(log_config_append=self.log_config_append)
        with mock.patch('logging.config.fileConfig') as fileConfig:
            log.setup('test_log_config_append')

        fileConfig.assert_called_once_with(self.log_config_append,
                                           disable_existing_loggers=False)


class MaskPasswordTestCase(test.BaseTestCase):

    def test_json(self):
        # Test 'adminPass' w/o spaces
        payload = """{'adminPass':'mypassword'}"""
        expected = """{'adminPass':'***'}"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'adminPass' with spaces
        payload = """{ 'adminPass' : 'mypassword' }"""
        expected = """{ 'adminPass' : '***' }"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'admin_pass' w/o spaces
        payload = """{'admin_pass':'mypassword'}"""
        expected = """{'admin_pass':'***'}"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'admin_pass' with spaces
        payload = """{ 'admin_pass' : 'mypassword' }"""
        expected = """{ 'admin_pass' : '***' }"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'password' w/o spaces
        payload = """{'password':'mypassword'}"""
        expected = """{'password':'***'}"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'password' with spaces
        payload = """{ 'password' : 'mypassword' }"""
        expected = """{ 'password' : '***' }"""
        self.assertEqual(expected, log.mask_password(payload))

    def test_xml(self):
        # Test 'adminPass' w/o spaces
        payload = """<adminPass>mypassword</adminPass>"""
        expected = """<adminPass>***</adminPass>"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'adminPass' with spaces
        payload = """<adminPass>
                        mypassword
                     </adminPass>"""
        expected = """<adminPass>***</adminPass>"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'admin_pass' w/o spaces
        payload = """<admin_pass>mypassword</admin_pass>"""
        expected = """<admin_pass>***</admin_pass>"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'admin_pass' with spaces
        payload = """<admin_pass>
                        mypassword
                     </admin_pass>"""
        expected = """<admin_pass>***</admin_pass>"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'password' w/o spaces
        payload = """<password>mypassword</password>"""
        expected = """<password>***</password>"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'password' with spaces
        payload = """<password>
                        mypassword
                     </password>"""
        expected = """<password>***</password>"""
        self.assertEqual(expected, log.mask_password(payload))

    def test_xml_attribute(self):
        # Test 'adminPass' w/o spaces
        payload = """adminPass='mypassword'"""
        expected = """adminPass='***'"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'adminPass' with spaces
        payload = """adminPass = 'mypassword'"""
        expected = """adminPass = '***'"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'adminPass' with double quotes
        payload = """adminPass = "mypassword\""""
        expected = """adminPass = "***\""""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'admin_pass' w/o spaces
        payload = """admin_pass='mypassword'"""
        expected = """admin_pass='***'"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'admin_pass' with spaces
        payload = """admin_pass = 'mypassword'"""
        expected = """admin_pass = '***'"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'admin_pass' with double quotes
        payload = """admin_pass = "mypassword\""""
        expected = """admin_pass = "***\""""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'password' w/o spaces
        payload = """password='mypassword'"""
        expected = """password='***'"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'password' with spaces
        payload = """password = 'mypassword'"""
        expected = """password = '***'"""
        self.assertEqual(expected, log.mask_password(payload))
        # Test 'password' with double quotes
        payload = """password = "mypassword\""""
        expected = """password = "***\""""
        self.assertEqual(expected, log.mask_password(payload))

    def test_json_message(self):
        payload = """body: {"changePassword": {"adminPass": "1234567"}}"""
        expected = """body: {"changePassword": {"adminPass": "***"}}"""
        self.assertEqual(expected, log.mask_password(payload))
        payload = """body: {"rescue": {"admin_pass": "1234567"}}"""
        expected = """body: {"rescue": {"admin_pass": "***"}}"""
        self.assertEqual(expected, log.mask_password(payload))
        payload = """body: {"rescue": {"password": "1234567"}}"""
        expected = """body: {"rescue": {"password": "***"}}"""
        self.assertEqual(expected, log.mask_password(payload))

    def test_xml_message(self):
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<rebuild
    xmlns="http://docs.openstack.org/compute/api/v1.1"
    name="foobar"
    imageRef="http://openstack.example.com/v1.1/32278/images/70a599e0-31e7"
    accessIPv4="1.2.3.4"
    accessIPv6="fe80::100"
    adminPass="seekr3t">
  <metadata>
    <meta key="My Server Name">Apache1</meta>
  </metadata>
</rebuild>"""
        expected = """<?xml version="1.0" encoding="UTF-8"?>
<rebuild
    xmlns="http://docs.openstack.org/compute/api/v1.1"
    name="foobar"
    imageRef="http://openstack.example.com/v1.1/32278/images/70a599e0-31e7"
    accessIPv4="1.2.3.4"
    accessIPv6="fe80::100"
    adminPass="***">
  <metadata>
    <meta key="My Server Name">Apache1</meta>
  </metadata>
</rebuild>"""
        self.assertEqual(expected, log.mask_password(payload))
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<rescue xmlns="http://docs.openstack.org/compute/api/v1.1"
    admin_pass="MySecretPass"/>"""
        expected = """<?xml version="1.0" encoding="UTF-8"?>
<rescue xmlns="http://docs.openstack.org/compute/api/v1.1"
    admin_pass="***"/>"""
        self.assertEqual(expected, log.mask_password(payload))
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<rescue xmlns="http://docs.openstack.org/compute/api/v1.1"
    password="MySecretPass"/>"""
        expected = """<?xml version="1.0" encoding="UTF-8"?>
<rescue xmlns="http://docs.openstack.org/compute/api/v1.1"
    password="***"/>"""
        self.assertEqual(expected, log.mask_password(payload))

    def test_mask_password(self):
        payload = "test = 'password'  :   'aaaaaa'"
        expected = "test = 'password'  :   '111'"
        self.assertEqual(expected, log.mask_password(payload, secret='111'))

        payload = 'test = "original_password" : "aaaaaaaaa"'
        expected = 'test = "original_password" : "***"'
        self.assertEqual(expected, log.mask_password(payload))

        payload = 'test = "param1" : "value"'
        expected = 'test = "param1" : "value"'
        self.assertEqual(expected, log.mask_password(payload))

        payload = """{'adminPass':'mypassword'}"""
        payload = unicode(payload)
        expected = """{'adminPass':'***'}"""
        self.assertEqual(expected, log.mask_password(payload))
