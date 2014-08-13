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
import tempfile

import mock
from oslo.config import cfg
from oslotest import base as test_base
from oslotest import moxstubout
import six

from openstack.common import context
from openstack.common import fileutils
from openstack.common.fixture import config
from openstack.common import gettextutils
from openstack.common import jsonutils
from openstack.common import local
from openstack.common import log
from openstack.common import log_handler
from openstack.common.notifier import api as notifier


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
        log._setup_logging_from_conf('test', 'test')

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


class LoggerTestCase(CommonLoggerTestsMixIn, test_base.BaseTestCase):
    def setUp(self):
        super(LoggerTestCase, self).setUp()
        self.log = log.getLogger(None)


class LazyLoggerTestCase(CommonLoggerTestsMixIn, test_base.BaseTestCase):
    def setUp(self):
        super(LazyLoggerTestCase, self).setUp()
        self.log = log.getLazyLogger(None)


class LogTestBase(test_base.BaseTestCase):
    """Base test class that provides some convenience functions."""
    def _add_handler_with_cleanup(self, log_instance, handler=None,
                                  formatter=None):
        """Add a log handler to a log instance.

        This function should be used to add handlers to loggers in test cases
        instead of directly adding them to ensure that the handler is
        correctly removed at the end of the test.  Otherwise the handler may
        be left on the logger and interfere with subsequent tests.

        :param log_instance: The log instance to which the handler will be
            added.
        :param handler: The handler class to be added.  Must be the class
            itself, not an instance.
        :param formatter: The formatter class to set on the handler.  Must be
            the class itself, not an instance.
        """
        self.stream = six.StringIO()
        if handler is None:
            handler = logging.StreamHandler
        self.handler = handler(self.stream)
        if formatter is None:
            formatter = log.ContextFormatter
        self.handler.setFormatter(formatter())
        log_instance.logger.addHandler(self.handler)
        self.addCleanup(log_instance.logger.removeHandler, self.handler)

    def _set_log_level_with_cleanup(self, log_instance, level):
        """Set the log level of a logger for the duration of a test.

        Use this function to set the log level of a logger and add the
        necessary cleanup to reset it back to default at the end of the test.

        :param log_instance: The logger whose level will be changed.
        :param level: The new log level to use.
        """
        self.level = log_instance.logger.getEffectiveLevel()
        log_instance.logger.setLevel(level)
        self.addCleanup(log_instance.logger.setLevel, self.level)


class LogHandlerTestCase(test_base.BaseTestCase):

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
        self.assertIsNone(log._get_log_file_path(binary='foo-bar'))

    def test_log_path_logfile_overrides_logdir(self):
        self.config(log_dir='/some/other/path',
                    log_file='/some/path/foo-bar.log')
        self.assertEqual(log._get_log_file_path(binary='foo-bar'),
                         '/some/path/foo-bar.log')


class SysLogHandlersTestCase(test_base.BaseTestCase):
    """Test for standard and RFC compliant Syslog handlers."""
    def setUp(self):
        super(SysLogHandlersTestCase, self).setUp()
        self.facility = logging.handlers.SysLogHandler.LOG_USER
        self.rfclogger = log.RFCSysLogHandler(facility=self.facility)
        self.rfclogger.binary_name = 'Foo_application'
        self.logger = logging.handlers.SysLogHandler(facility=self.facility)
        self.logger.binary_name = 'Foo_application'

    def test_rfc_format(self):
        """Ensure syslog msg contains APP-NAME for RFC wrapped handler."""
        logrecord = logging.LogRecord('name', 'WARN', '/tmp', 1,
                                      'Message', None, None)
        expected = logging.LogRecord('name', 'WARN', '/tmp', 1,
                                     'Foo_application Message', None, None)
        self.assertEqual(self.rfclogger.format(logrecord),
                         expected.getMessage())

    def test_standard_format(self):
        """Ensure syslog msg isn't modified for standard handler."""
        logrecord = logging.LogRecord('name', 'WARN', '/tmp', 1,
                                      'Message', None, None)
        expected = logrecord
        self.assertEqual(self.logger.format(logrecord),
                         expected.getMessage())


class PublishErrorsHandlerTestCase(test_base.BaseTestCase):
    """Tests for log.PublishErrorsHandler."""
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

    def test_emit_with_args(self):
        """Make sure emit the message which merged user-supplied arguments."""
        self.config(notification_driver=[
            'openstack.common.notifier.rabbit_notifier'
        ])
        self.emit_payload = None
        expect_payload = dict(error="msg with args: show me")

        def fake_notifier(_context, _publisher_id, _event_type, _priority,
                          payload):
            self.emit_payload = payload

        self.stubs.Set(notifier, 'notify', fake_notifier)
        logrecord = logging.LogRecord('name', 'WARN', '/tmp', 1,
                                      'msg with args: %s', 'show me', None)
        self.publiserrorshandler.emit(logrecord)
        self.assertEqual(self.emit_payload, expect_payload)


class LogLevelTestCase(test_base.BaseTestCase):
    def setUp(self):
        super(LogLevelTestCase, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        levels = self.CONF.default_log_levels
        levels.append("nova-test=AUDIT")
        levels.append("nova-not-debug=WARN")
        self.config = self.useFixture(config.Config()).config
        self.config(default_log_levels=levels,
                    verbose=True)
        log.setup('testing')
        self.log = log.getLogger('nova-test')
        self.log_no_debug = log.getLogger('nova-not-debug')

    def test_is_enabled_for(self):
        self.assertTrue(self.log.isEnabledFor(logging.AUDIT))
        self.assertFalse(self.log_no_debug.isEnabledFor(logging.DEBUG))

    def test_has_level_from_flags(self):
        self.assertEqual(logging.AUDIT, self.log.logger.getEffectiveLevel())

    def test_child_log_has_level_of_parent_flag(self):
        l = log.getLogger('nova-test.foo')
        self.assertEqual(logging.AUDIT, l.logger.getEffectiveLevel())


class JSONFormatterTestCase(LogTestBase):
    def setUp(self):
        super(JSONFormatterTestCase, self).setUp()
        self.log = log.getLogger('test-json')
        self._add_handler_with_cleanup(self.log, formatter=log.JSONFormatter)
        self._set_log_level_with_cleanup(self.log, logging.DEBUG)

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


class ContextFormatterTestCase(LogTestBase):
    def setUp(self):
        super(ContextFormatterTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config
        self.config(logging_context_format_string="HAS CONTEXT "
                                                  "[%(request_id)s]: "
                                                  "%(message)s",
                    logging_default_format_string="NOCTXT: %(message)s",
                    logging_debug_format_suffix="--DBG")
        self.log = log.getLogger('')  # obtain root logger instead of 'unknown'
        self._add_handler_with_cleanup(self.log)
        self._set_log_level_with_cleanup(self.log, logging.DEBUG)

    def test_uncontextualized_log(self):
        self.log.info("foo")
        self.assertEqual("NOCTXT: foo\n", self.stream.getvalue())

    def test_contextualized_log(self):
        ctxt = _fake_context()
        self.log.info("bar", context=ctxt)
        expected = "HAS CONTEXT [%s]: bar\n" % ctxt.request_id
        self.assertEqual(expected, self.stream.getvalue())

    def test_context_is_taken_from_tls_variable(self):
        ctxt = _fake_context()
        local.store.context = ctxt
        try:
            self.log.info("bar")
            expected = "HAS CONTEXT [%s]: bar\n" % ctxt.request_id
            self.assertEqual(expected, self.stream.getvalue())
        finally:
            del local.store.context

    def test_contextual_information_is_imparted_to_3rd_party_log_records(self):
        ctxt = _fake_context()
        local.store.context = ctxt
        try:
            sa_log = logging.getLogger('sqlalchemy.engine')
            sa_log.setLevel(logging.INFO)
            sa_log.info('emulate logging within sqlalchemy')

            expected = ("HAS CONTEXT [%s]: emulate logging within "
                        "sqlalchemy\n" % ctxt.request_id)
            self.assertEqual(expected, self.stream.getvalue())
        finally:
            del local.store.context

    def test_message_logging_3rd_party_log_records(self):
        ctxt = _fake_context()
        local.store.context = ctxt
        local.store.context.request_id = six.text_type('99')
        try:
            sa_log = logging.getLogger('sqlalchemy.engine')
            sa_log.setLevel(logging.INFO)
            message = gettextutils.Message('test ' + six.unichr(128))
            sa_log.info(message)

            expected = ("HAS CONTEXT [%s]: %s\n" % (ctxt.request_id,
                                                    six.text_type(message)))
            self.assertEqual(expected, self.stream.getvalue())
        finally:
            del local.store.context

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
        message = gettextutils.Message('test ' + six.unichr(128))
        self.log.info(message, context=ctxt)
        expected = "HAS CONTEXT [%s]: %s\n" % (ctxt.request_id,
                                               six.text_type(message))
        self.assertEqual(expected, self.stream.getvalue())

    def test_unicode_conversion_in_adapter(self):
        ctxt = _fake_context()
        ctxt.request_id = six.text_type('99')
        message = "Exception is (%s)"
        ex = Exception(gettextutils.Message('test' + six.unichr(128)))
        self.log.debug(message, ex, context=ctxt)
        message = six.text_type(message) % ex
        expected = "HAS CONTEXT [%s]: %s --DBG\n" % (ctxt.request_id,
                                                     message)
        self.assertEqual(expected, self.stream.getvalue())

    def test_unicode_conversion_in_formatter(self):
        ctxt = _fake_context()
        local.store.context = ctxt
        ctxt.request_id = six.text_type('99')
        try:
            no_adapt_log = logging.getLogger('no_adapt')
            no_adapt_log.setLevel(logging.INFO)
            message = "Exception is (%s)"
            ex = Exception(gettextutils.Message('test' + six.unichr(128)))
            no_adapt_log.info(message, ex)
            message = six.text_type(message) % ex
            expected = "HAS CONTEXT [%s]: %s\n" % (ctxt.request_id,
                                                   message)
            self.assertEqual(expected, self.stream.getvalue())
        finally:
            del local.store.context


class ExceptionLoggingTestCase(LogTestBase):
    """Test that Exceptions are logged."""

    def test_excepthook_logs_exception(self):
        product_name = 'somename'
        exc_log = log.getLogger(product_name)

        self._add_handler_with_cleanup(exc_log)
        excepthook = log._create_logging_excepthook(product_name)

        try:
            raise Exception('Some error happened')
        except Exception:
            excepthook(*sys.exc_info())

        expected_string = ("CRITICAL somename [-] "
                           "Exception: Some error happened")
        self.assertTrue(expected_string in self.stream.getvalue(),
                        msg="Exception is not logged")

    def test_excepthook_installed(self):
        log.setup("test_excepthook_installed")
        self.assertTrue(sys.excepthook != sys.__excepthook__)


class FancyRecordTestCase(LogTestBase):
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
        self.colorlog = log.getLogger()
        self._add_handler_with_cleanup(self.colorlog, log.ColorHandler)
        self._set_log_level_with_cleanup(self.colorlog, logging.DEBUG)

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


class DomainTestCase(LogTestBase):
    def setUp(self):
        super(DomainTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config
        self.config(logging_context_format_string="[%(request_id)s]: "
                                                  "%(user_identity)s "
                                                  "%(message)s")
        self.mylog = log.getLogger()
        self._add_handler_with_cleanup(self.mylog)
        self._set_log_level_with_cleanup(self.mylog, logging.DEBUG)

    def _validate_keys(self, ctxt, keyed_log_string):
        infoexpected = "%s info\n" % (keyed_log_string)
        warnexpected = "%s warn\n" % (keyed_log_string)

        self.mylog.info("info", context=ctxt)
        self.assertEqual(infoexpected, self.stream.getvalue())

        self.mylog.warn("warn", context=ctxt)
        self.assertEqual(infoexpected + warnexpected, self.stream.getvalue())

    def test_domain_in_log_msg(self):
        ctxt = _fake_context()
        ctxt.domain = 'mydomain'
        ctxt.project_domain = 'myprojectdomain'
        ctxt.user_domain = 'myuserdomain'
        user_identity = ctxt.to_dict()['user_identity']
        self.assertTrue(ctxt.domain in user_identity)
        self.assertTrue(ctxt.project_domain in user_identity)
        self.assertTrue(ctxt.user_domain in user_identity)
        self._validate_keys(ctxt, ('[%s]: %s' %
                                   (ctxt.request_id, user_identity)))


class SetDefaultsTestCase(test_base.BaseTestCase):
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

        self._orig_defaults = dict([(o.dest, o.default)
                                    for o in log.log_opts])
        self.addCleanup(self._restore_log_defaults)

    def _restore_log_defaults(self):
        for opt in log.log_opts:
            opt.default = self._orig_defaults[opt.dest]

    def test_default_log_level_to_none(self):
        log.set_defaults(logging_context_format_string=None,
                         default_log_levels=None)
        self.conf([])
        self.assertEqual(log.DEFAULT_LOG_LEVELS, self.conf.default_log_levels)

    def test_change_default(self):
        my_default = '%(asctime)s %(levelname)s %(name)s [%(request_id)s '\
                     '%(user_id)s %(project)s] %(instance)s'\
                     '%(message)s'
        log.set_defaults(logging_context_format_string=my_default)
        self.conf([])
        self.assertEqual(self.conf.logging_context_format_string, my_default)

    def test_change_default_log_level(self):
        log.set_defaults(default_log_levels=['foo=bar'])
        self.conf([])
        self.assertEqual(['foo=bar'], self.conf.default_log_levels)
        self.assertIsNotNone(self.conf.logging_context_format_string)


class LogConfigOptsTestCase(test_base.BaseTestCase):

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

        self.assertIsNone(self.CONF.log_config_append)
        self.assertIsNone(self.CONF.log_file)
        self.assertIsNone(self.CONF.log_dir)
        self.assertIsNone(self.CONF.log_format)

        self.assertEqual(self.CONF.log_date_format,
                         log._DEFAULT_LOG_DATE_FORMAT)

        self.assertEqual(self.CONF.use_syslog, False)
        self.assertEqual(self.CONF.use_syslog_rfc_format, False)

    def test_log_file(self):
        log_file = '/some/path/foo-bar.log'
        self.CONF(['--log-file', log_file])
        self.assertEqual(self.CONF.log_file, log_file)

    def test_log_dir_handlers(self):
        log_dir = tempfile.mkdtemp()
        self.CONF(['--log-dir', log_dir])
        self.CONF.set_default('use_stderr', False)
        log._setup_logging_from_conf('test', 'test')
        logger = log._loggers[None].logger
        self.assertEqual(1, len(logger.handlers))
        self.assertIsInstance(logger.handlers[0],
                              logging.handlers.WatchedFileHandler)

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
        log._setup_logging_from_conf('test', 'test')
        logger = log._loggers[None].logger
        for handler in logger.handlers:
            formatter = handler.formatter
            self.assertTrue(isinstance(formatter, logging.Formatter))

    def test_default_formatter(self):
        log._setup_logging_from_conf('test', 'test')
        logger = log._loggers[None].logger
        for handler in logger.handlers:
            formatter = handler.formatter
            self.assertTrue(isinstance(formatter, log.ContextFormatter))


class LogConfigTestCase(test_base.BaseTestCase):

    minimal_config = b"""[loggers]
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
