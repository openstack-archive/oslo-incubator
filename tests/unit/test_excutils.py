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
import mox
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

    def my_time_sleep(self, arg):
        pass

    def common_exc_retrier_init(self):
        self.stubs.Set(time, 'sleep', self.my_time_sleep)
        self.mox.StubOutWithMock(logging, 'exception')
        self.mox.StubOutWithMock(time, 'time')
        self.exception_count = 0

    def test_exc_retrier_1exc_gives_1log(self):
        self.common_exc_retrier_init()
        time.time().AndReturn(1)
        logging.exception(mox.In('Unexpected exception occurred 1 time(s)'))
        self.mox.ReplayAll()
        self.exception_tuple = ('unexpected',)
        self.exception_generator()
        self.addCleanup(self.stubs.UnsetAll)

    def test_exc_retrier_same_10exc_1min_gives_1log(self):
        self.common_exc_retrier_init()
        time.time().AndReturn(1)
        logging.exception(mox.In('Unexpected exception occurred 1 time(s)'))
        for i in range(2,11):
            time.time().AndReturn(i)
        self.mox.ReplayAll()
        self.exception_tuple = ('unexpected',) * 10
        self.exception_generator()
        self.addCleanup(self.stubs.UnsetAll)

    def test_exc_retrier_same_2exc_2min_gives_2logs(self):
        self.common_exc_retrier_init()
        time.time().AndReturn(1)
        logging.exception(mox.In('Unexpected exception occurred 1 time(s)'))
        time.time().AndReturn(65)
        logging.exception(mox.In('Unexpected exception occurred 1 time(s)'))
        self.mox.ReplayAll()
        self.exception_tuple = ('unexpected',) * 2
        self.exception_generator()
        self.addCleanup(self.stubs.UnsetAll)

    def test_exc_retrier_same_10exc_2min_gives_2logs(self):
        self.common_exc_retrier_init()
        time.time().AndReturn(1)
        logging.exception(mox.In('Unexpected exception occurred 1 time(s)'))
        time.time().AndReturn(12)
        time.time().AndReturn(23)
        time.time().AndReturn(34)
        time.time().AndReturn(45)
        time.time().AndReturn(106)
        logging.exception(mox.In('Unexpected exception occurred 5 time(s)'))
        time.time().AndReturn(117)
        time.time().AndReturn(128)
        time.time().AndReturn(139)
        time.time().AndReturn(150)
        self.mox.ReplayAll()
        self.exception_tuple = ('unexpected',) * 10
        self.exception_generator()
        self.addCleanup(self.stubs.UnsetAll)

    def test_exc_retrier_mixed_4exc_1min_gives_2logs(self):
        self.common_exc_retrier_init()
        time.time().AndReturn(1)
        logging.exception(mox.In('Unexpected exception occurred 1 time(s)'))
        time.time().AndReturn(10)
        time.time().AndReturn(20)
        logging.exception(mox.In('Unexpected exception occurred 1 time(s)'))
        time.time().AndReturn(30)
        self.mox.ReplayAll()
        self.exception_tuple = ('unexpected 1', 'unexpected 1',
                                'unexpected 2', 'unexpected 2')
        self.exception_generator()
        self.addCleanup(self.stubs.UnsetAll)

    def test_exc_retrier_mixed_4exc_2min_gives_2logs(self):
        self.common_exc_retrier_init()
        time.time().AndReturn(1)
        logging.exception(mox.In('Unexpected exception occurred 1 time(s)'))
        time.time().AndReturn(10)
        time.time().AndReturn(100)
        logging.exception(mox.In('Unexpected exception occurred 1 time(s)'))
        time.time().AndReturn(110)
        self.mox.ReplayAll()
        self.exception_tuple = ('unexpected 1', 'unexpected 1',
                                'unexpected 2', 'unexpected 2')
        self.exception_generator()
        self.addCleanup(self.stubs.UnsetAll)

    def test_exc_retrier_mixed_4exc_2min_gives_3logs(self):
        self.common_exc_retrier_init()
        time.time().AndReturn(1)
        logging.exception(mox.In('Unexpected exception occurred 1 time(s)'))
        time.time().AndReturn(10)
        time.time().AndReturn(100)
        logging.exception(mox.In('Unexpected exception occurred 2 time(s)'))
        time.time().AndReturn(110)
        logging.exception(mox.In('Unexpected exception occurred 1 time(s)'))
        self.mox.ReplayAll()
        self.exception_tuple = ('unexpected 1', 'unexpected 1',
                                'unexpected 1', 'unexpected 2')
        self.exception_generator()
        self.addCleanup(self.stubs.UnsetAll)
