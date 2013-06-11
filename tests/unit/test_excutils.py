# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012, Red Hat, Inc.
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

import inspect
import logging
import time

from openstack.common import excutils
from tests import utils


class SaveAndReraiseTest(utils.BaseTestCase):

    def test_save_and_reraise_exception(self):
        e = None
        msg = 'foo'
        try:
            try:
                raise Exception(msg)
            except Exception:
                with excutils.save_and_reraise_exception():
                    pass
        except Exception as _e:
            e = _e

        self.assertEqual(str(e), msg)

    def test_save_and_reraise_exception_dropped(self):
        e = None
        msg = 'second exception'
        try:
            try:
                raise Exception('dropped')
            except Exception:
                with excutils.save_and_reraise_exception():
                    raise Exception(msg)
        except Exception as _e:
            e = _e

        self.assertEqual(str(e), msg)


class ForeverRetryUncaughtExceptionsTest(utils.BaseTestCase):

    @excutils.forever_retry_uncaught_exceptions
    def exception_generator(self):
        if self.exception_count == len(self.exception_tuple):
            return
        self.exception_count += 1
        raise Exception(self.exception_tuple[self.exception_count - 1])

    def my_exception_logger(self, msg, *args, **kwargs):
        self.assertTrue(
            self.log_msg_tuple[self.my_exception_logger_calls] in msg)
        self.my_exception_logger_calls += 1
        self.orig_exception_logger(msg, *args, **kwargs)

    def my_time_time(self):
        # only worry about time calls from the decorator
        if inspect.stack()[1][3] != 'inner_func':
            return 0
        self.my_time_calls += 1
        return self.time_tuple[self.my_time_calls - 1]

    def my_time_sleep(self, arg):
        pass

    def common_exc_retrier(self):
        self.exception_count = 0
        self.my_exception_logger_calls = 0
        self.my_time_calls = 0
        self.orig_exception_logger = logging.exception
        self.stubs.Set(logging, 'exception', self.my_exception_logger)
        self.stubs.Set(time, 'time', self.my_time_time)
        self.stubs.Set(time, 'sleep', self.my_time_sleep)
        self.exception_generator()
        self.assertEqual(self.my_exception_logger_calls,
                         len(self.log_msg_tuple))
        self.stubs.UnsetAll()

    def test_exc_retrier_1exc_gives_1log(self):
        self.exception_tuple = ('unexpected',)
        self.log_msg_tuple = ('Unexpected exception... retrying.',)
        self.time_tuple = (1,)
        self.common_exc_retrier()

    def test_exc_retrier_same_10exc_1min_gives_1log(self):
        self.exception_tuple = ('unexpected',) * 10
        self.log_msg_tuple = ('Unexpected exception... retrying.',)
        self.time_tuple = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
        self.common_exc_retrier()

    def test_exc_retrier_same_2exc_2min_gives_2logs(self):
        self.exception_tuple = ('unexpected',) * 2
        self.log_msg_tuple = ('Unexpected exception... retrying.',) * 2
        self.time_tuple = (1, 65)
        self.common_exc_retrier()

    def test_exc_retrier_same_10exc_2min_gives_2logs(self):
        self.exception_tuple = ('unexpected',) * 10
        self.log_msg_tuple = ('Unexpected exception... retrying.',
                              'Unexpected exception occurred 5 times')
        self.time_tuple = (1, 12, 23, 34, 45, 106, 117, 128, 139, 150)
        self.common_exc_retrier()

    def test_exc_retrier_mixed_4exc_1min_gives_2logs(self):
        self.exception_tuple = ('unexpected 1', 'unexpected 1',
                                'unexpected 2', 'unexpected 2')
        self.log_msg_tuple = ('Unexpected exception... retrying.',) * 2
        self.time_tuple = (1, 10, 20, 30)
        self.common_exc_retrier()

    def test_exc_retrier_mixed_4exc_2min_gives_2logs(self):
        self.exception_tuple = ('unexpected 1', 'unexpected 1',
                                'unexpected 2', 'unexpected 2')
        self.log_msg_tuple = ('Unexpected exception... retrying.',) * 2
        self.time_tuple = (1, 10, 100, 110)
        self.common_exc_retrier()

    def test_exc_retrier_mixed_4exc_2min_gives_3logs(self):
        self.exception_tuple = ('unexpected 1', 'unexpected 1',
                                'unexpected 1', 'unexpected 2')
        self.log_msg_tuple = ('Unexpected exception... retrying.',
                              'Unexpected exception occurred 2 times',
                              'Unexpected exception... retrying.')
        self.time_tuple = (1, 10, 100, 110)
        self.common_exc_retrier()
