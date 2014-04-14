#
#    Copyright 2010 OpenStack Foundation
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

try:
    import mock
except ImportError:
    import unittest.mock as mock

from openstack.common.fixture import config
from openstack.common.fixture import mockpatch
from openstack.common import log as logging
from openstack.common import test

LOG = logging.getLogger(__name__)


class DeprecatedConfigTestCase(test.BaseTestCase):
    def setUp(self):
        super(DeprecatedConfigTestCase, self).setUp()

        warn_fixture = self.useFixture(mockpatch.PatchObject(LOG, 'warn'))
        self.warn_mock = warn_fixture.mock

        crit_fixture = self.useFixture(mockpatch.PatchObject(LOG, 'critical'))
        self.crit_mock = crit_fixture.mock

        self.config = self.useFixture(config.Config()).config

    def test_deprecated(self):
        LOG.deprecated('test')
        self.warn_mock.assert_called_once_with('Deprecated: test')
        self.assertFalse(self.crit_mock.called)

    def test_deprecated_fatal(self):
        self.config(fatal_deprecations=True)
        self.assertRaises(logging.DeprecatedConfig,
                          LOG.deprecated, "test2")
        self.crit_mock.assert_called_once_with('Deprecated: test2')
        self.assertFalse(self.warn_mock.called)

    def test_deprecated_logs_only_once(self):
        # If the same message is used multiple times then it's only logged
        # once.

        LOG.deprecated('only once!')
        LOG.deprecated('only once!')
        LOG.deprecated('only once!')

        self.warn_mock.assert_called_once_with('Deprecated: only once!')

    def test_deprecated_logs_once_diff_messages(self):
        # If different messages are used, you get one log per message.
        msg1 = 'tdlodm_message 1'
        msg2 = 'tdlodm_message 2'

        LOG.deprecated(msg1)
        LOG.deprecated(msg2)
        LOG.deprecated(msg1)
        LOG.deprecated(msg1)
        LOG.deprecated(msg2)
        LOG.deprecated(msg2)

        exp_calls = [
            mock.call('Deprecated: tdlodm_message 1'),
            mock.call('Deprecated: tdlodm_message 2'),
        ]
        self.warn_mock.assert_has_calls(exp_calls)
        self.assertEqual(2, self.warn_mock.call_count)

    def test_deprecated_logs_different_arg_simple(self):
        # If the same message format with different arguments is used then each
        # set of message + argument is logged once (for a simple argument)

        LOG.deprecated('only once! %s', 'arg1')
        LOG.deprecated('only once! %s', 'arg1')
        LOG.deprecated('only once! %s', 'arg2')
        LOG.deprecated('only once! %s', 'arg2')

        exp_calls = [
            mock.call('Deprecated: only once! %s', 'arg1'),
            mock.call('Deprecated: only once! %s', 'arg2'),
        ]
        self.warn_mock.assert_has_calls(exp_calls)
        self.assertEqual(2, self.warn_mock.call_count)

    def test_deprecated_logs_different_arg_complex(self):
        # If the same message format with different arguments is used then each
        # set of message + argument is logged once (for more complex arguments)

        msg_fmt_1 = 'tdldac_msg 1 %(arg1)s %(arg2)s'
        msg_fmt_1_arg_1 = {'arg1': 'val1_1', 'arg2': 'val2_1'}
        msg_fmt_1_arg_2 = {'arg1': 'val1_2', 'arg2': 'val2_2'}

        msg_fmt_2 = 'tdldac_msg 2 %s %s %s'
        msg_fmt_2_arg_1 = 3, 4, 5
        msg_fmt_2_arg_2 = 6, None, 'purple'
        msg_fmt_2_arg_3 = 6, None, 'something'  # same first args.

        LOG.deprecated(msg_fmt_1, msg_fmt_1_arg_1)
        LOG.deprecated(msg_fmt_1, msg_fmt_1_arg_2)  # logged: args different
        LOG.deprecated(msg_fmt_1, msg_fmt_1_arg_1)  # no log: same msg+args

        LOG.deprecated(msg_fmt_2, msg_fmt_2_arg_1)
        LOG.deprecated(msg_fmt_2, *msg_fmt_2_arg_2)  # logged: args different
        LOG.deprecated(msg_fmt_2, *msg_fmt_2_arg_3)  # logged: args different
        LOG.deprecated(msg_fmt_2, *msg_fmt_2_arg_3)  # no log: same msg+args
        LOG.deprecated(msg_fmt_2, *msg_fmt_2_arg_2)  # no log: same msg+args

        exp_calls = [
            mock.call('Deprecated: %s' % msg_fmt_1, msg_fmt_1_arg_1),
            mock.call('Deprecated: %s' % msg_fmt_1, msg_fmt_1_arg_2),
            mock.call('Deprecated: %s' % msg_fmt_2, msg_fmt_2_arg_1),
            mock.call('Deprecated: %s' % msg_fmt_2, *msg_fmt_2_arg_2),
            mock.call('Deprecated: %s' % msg_fmt_2, *msg_fmt_2_arg_3),
        ]
        self.warn_mock.assert_has_calls(exp_calls)
        self.assertEqual(5, self.warn_mock.call_count)
