import cStringIO
import logging
import sys

from openstack.common import context
from openstack.common import cfg
from openstack.common import jsonutils
from openstack.common import log
from openstack.common.notifier import api as notifier
from openstack.common.notifier import list_notifier
from tests import utils as test_utils

CONF = cfg.CONF


def _fake_context():
    return context.RequestContext(1, 1)


class LoggerTestCase(test_utils.BaseTestCase):
    def setUp(self):
        super(LoggerTestCase, self).setUp()
        self.log = log.getLogger()

    def test_handlers_have_legacy_formatter(self):
        formatters = []
        for h in self.log.logger.handlers:
            f = h.formatter
            if isinstance(f, log.LegacyFormatter):
                formatters.append(f)
        self.assert_(formatters)
        self.assertEqual(len(formatters), len(self.log.logger.handlers))

    def test_handles_context_kwarg(self):
        self.log.info("foo", context=_fake_context())
        self.assert_(True)  # didn't raise exception

    def test_audit_handles_context_arg(self):
        self.log.audit("foo", context=_fake_context())
        self.assert_(True)  # didn't raise exception

    def test_will_be_verbose_if_verbose_flag_set(self):
        self.config(verbose=True)
        log.setup()
        self.assertEqual(logging.DEBUG, self.log.logger.getEffectiveLevel())

    def test_will_not_be_verbose_if_verbose_flag_not_set(self):
        self.config(verbose=False)
        log.setup()
        self.assertEqual(logging.INFO, self.log.logger.getEffectiveLevel())

    def test_no_logging_via_module(self):
        for func in ('critical', 'error', 'exception', 'warning', 'warn',
                     'info', 'debug', 'log', 'audit'):
            self.assertRaises(AttributeError, getattr, log, func)


class LogHandlerTestCase(test_utils.BaseTestCase):
    def test_log_path_logdir(self):
        self.config(logdir='/some/path', logfile=None)
        self.assertEquals(log._get_log_file_path(binary='foo-bar'),
                          '/some/path/foo-bar.log')

    def test_log_path_logfile(self):
        self.config(logfile='/some/path/foo-bar.log')
        self.assertEquals(log._get_log_file_path(binary='foo-bar'),
                          '/some/path/foo-bar.log')

    def test_log_path_none(self):
        self.config(logdir=None, logfile=None)
        self.assertTrue(log._get_log_file_path(binary='foo-bar') is None)

    def test_log_path_logfile_overrides_logdir(self):
        self.config(logdir='/some/other/path',
                    logfile='/some/path/foo-bar.log')
        self.assertEquals(log._get_log_file_path(binary='foo-bar'),
                          '/some/path/foo-bar.log')


class PublishErrorsHandlerTestCase(test_utils.BaseTestCase):
    """Tests for log.PublishErrorsHandler"""
    def setUp(self):
        super(PublishErrorsHandlerTestCase, self).setUp()
        self.publiserrorshandler = log.PublishErrorsHandler(logging.ERROR)

    def test_emit_cfg_list_notifier_drivers_in_flags(self):
        self.stub_flg = False

        def fake_notifier(*args, **kwargs):
            self.stub_flg = True

        self.stubs.Set(notifier, 'notify', fake_notifier)
        logrecord = logging.LogRecord('name', 'WARN', '/tmp', 1,
                                      'Message', None, None)
        self.publiserrorshandler.emit(logrecord)
        self.assertTrue(self.stub_flg)

    def test_emit_cfg_log_notifier_in_list_notifier_drivers(self):
        self.config(list_notifier_drivers=[
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


class LoggerTestCase(test_utils.BaseTestCase):
    def setUp(self):
        super(LoggerTestCase, self).setUp()
        levels = CONF.default_log_levels
        levels.append("nova-test=AUDIT")
        self.config(default_log_levels=levels,
                    verbose=True)
        log.setup('testing')
        self.log = log.getLogger('nova-test')

    def test_has_level_from_flags(self):
        self.assertEqual(logging.AUDIT, self.log.logger.getEffectiveLevel())

    def test_child_log_has_level_of_parent_flag(self):
        l = log.getLogger('nova-test.foo')
        self.assertEqual(logging.AUDIT, l.logger.getEffectiveLevel())


class JSONFormatterTestCase(test_utils.BaseTestCase):
    def setUp(self):
        super(JSONFormatterTestCase, self).setUp()
        self.log = log.getLogger('test-json')
        self.stream = cStringIO.StringIO()
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


class LegacyFormatterTestCase(test_utils.BaseTestCase):
    def setUp(self):
        super(LegacyFormatterTestCase, self).setUp()
        self.config(logging_context_format_string="HAS CONTEXT "
                                                  "[%(request_id)s]: "
                                                  "%(message)s",
                    logging_default_format_string="NOCTXT: %(message)s",
                    logging_debug_format_suffix="--DBG")
        self.log = log.getLogger()
        self.stream = cStringIO.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(log.LegacyFormatter())
        self.log.logger.addHandler(self.handler)
        self.level = self.log.logger.getEffectiveLevel()
        self.log.logger.setLevel(logging.DEBUG)

    def tearDown(self):
        self.log.logger.setLevel(self.level)
        self.log.logger.removeHandler(self.handler)
        super(LegacyFormatterTestCase, self).tearDown()

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
