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

from openstack.common.fixture import config
from openstack.common.fixture import moxstubout
from openstack.common import log as logging
from openstack.common import test

LOG = logging.getLogger(__name__)


class DeprecatedConfigTestCase(test.BaseTestCase):
    def setUp(self):
        super(DeprecatedConfigTestCase, self).setUp()
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs
        self.config = self.useFixture(config.Config()).config

        self.warnbuffer = ""
        self.critbuffer = ""

        class LogFn(object):
            def __init__(self, obj, attr_name):
                self._obj = obj
                self._attr_name = attr_name

            def __call__(self, msg, *args):
                if args:
                    if len(args) == 1:
                        msg = msg % args[0]
                    else:
                        msg = msg % args
                new_buf = getattr(self._obj, self._attr_name) + msg + '\n'
                setattr(self._obj, self._attr_name, new_buf)

        self.stubs.Set(LOG, 'warn', LogFn(self, 'warnbuffer'))
        self.stubs.Set(LOG, 'critical', LogFn(self, 'critbuffer'))

    def test_deprecated(self):
        LOG.deprecated('test')
        self.assertEqual(self.warnbuffer, 'Deprecated: test\n')

    def test_deprecated_fatal(self):
        self.config(fatal_deprecations=True)
        self.assertRaises(logging.DeprecatedConfig,
                          LOG.deprecated, "test2")
        self.assertEqual(self.critbuffer, 'Deprecated: test2\n')

    def test_deprecated_logs_only_once(self):
        # If the same message is used multiple times then it's only logged
        # once.

        LOG.deprecated('only once!')
        LOG.deprecated('only once!')
        LOG.deprecated('only once!')

        # TODO(blk-u): This isn't working correctly, it should only log once,
        # see bug 1266812.
        # The following should be
        #   exp_log = 'Deprecated: only once!\n'
        #   self.assertEqual(exp_log, self.warnbuffer)

        exp_log = ('Deprecated: only once!\n'
                   'Deprecated: only once!\n'
                   'Deprecated: only once!\n')
        self.assertEqual(exp_log, self.warnbuffer)

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

        # TODO(blk-u): This isn't working correctly, see bug 1266812.
        # The following should be
        #   exp_log = ('Deprecated: tdlodm_message 1\n'
        #              'Deprecated: tdlodm_message 2\n')
        #   self.assertEqual(exp_log, self.warnbuffer)

        exp_log = ('Deprecated: tdlodm_message 1\n'
                   'Deprecated: tdlodm_message 2\n'
                   'Deprecated: tdlodm_message 1\n'
                   'Deprecated: tdlodm_message 1\n'
                   'Deprecated: tdlodm_message 2\n'
                   'Deprecated: tdlodm_message 2\n')
        self.assertEqual(exp_log, self.warnbuffer)

    def test_deprecated_logs_different_arg_simple(self):
        # If the same message format with different arguments is used then each
        # set of message + argument is logged once (for a simple argument)

        LOG.deprecated('only once! %s', 'arg1')
        LOG.deprecated('only once! %s', 'arg1')
        LOG.deprecated('only once! %s', 'arg2')
        LOG.deprecated('only once! %s', 'arg2')

        # TODO(blk-u): This isn't working correctly, see bug 1266812.
        # The following should be
        #   exp_log = ('Deprecated: only once! arg1\n'
        #              'Deprecated: only once! arg2\n')
        #   self.assertEqual(exp_log, self.warnbuffer)

        exp_log = ('Deprecated: only once! arg1\n'
                   'Deprecated: only once! arg1\n'
                   'Deprecated: only once! arg2\n'
                   'Deprecated: only once! arg2\n')
        self.assertEqual(exp_log, self.warnbuffer)

    def test_deprecated_logs_different_arg_complex(self):
        # If the same message format with different arguments is used then each
        # set of message + argument is logged once (for more complex arguments)

        msg_fmt_1 = 'tdldac_msg 1 %(arg1)s %(arg2)s'
        msg_fmt_1_arg_1 = {'arg1': 'val1_1', 'arg2': 'val2_1'}
        msg_fmt_1_arg_2 = {'arg1': 'val1_2', 'arg2': 'val2_2'}

        msg_fmt_2 = 'tdldac_msg 2 %s %s %s'
        msg_fmt_2_arg_1 = 3, 4, 5
        msg_fmt_2_arg_2 = 6, None, 'purple'
        msg_fmt_2_arg_3 = 6, None, 'something' # same first args.

        LOG.deprecated(msg_fmt_1, msg_fmt_1_arg_1)
        LOG.deprecated(msg_fmt_1, msg_fmt_1_arg_2)  # logged: args different
        LOG.deprecated(msg_fmt_1, msg_fmt_1_arg_1)  # no log: same msg+args

        LOG.deprecated(msg_fmt_2, msg_fmt_2_arg_1)
        LOG.deprecated(msg_fmt_2, *msg_fmt_2_arg_2)  # logged: args different
        LOG.deprecated(msg_fmt_2, *msg_fmt_2_arg_3)  # logged: args different
        LOG.deprecated(msg_fmt_2, *msg_fmt_2_arg_3)  # no log: same msg+args
        LOG.deprecated(msg_fmt_2, *msg_fmt_2_arg_2)  # no log: same msg+args

        # TODO(blk-u): This isn't working correctly, see bug 1266812.
        # The following should be
        #   exp_log = ('Deprecated: tdldac_msg 1 val1_1 val2_1\n'
        #              'Deprecated: tdldac_msg 1 val1_2 val2_2\n'
        #              'Deprecated: tdldac_msg 2 3 4 5\n'
        #              'Deprecated: tdldac_msg 2 6 None purple\n'
        #              'Deprecated: tdldac_msg 2 6 None something\n')
        #   self.assertEqual(exp_log, self.warnbuffer)

        exp_log = ('Deprecated: tdldac_msg 1 val1_1 val2_1\n'
                   'Deprecated: tdldac_msg 1 val1_2 val2_2\n'
                   'Deprecated: tdldac_msg 1 val1_1 val2_1\n'
                   'Deprecated: tdldac_msg 2 3 4 5\n'
                   'Deprecated: tdldac_msg 2 6 None purple\n'
                   'Deprecated: tdldac_msg 2 6 None something\n'
                   'Deprecated: tdldac_msg 2 6 None something\n'
                   'Deprecated: tdldac_msg 2 6 None purple\n')
        self.assertEqual(exp_log, self.warnbuffer)
