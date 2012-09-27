# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""
Unit Tests for remote procedure calls using queue
"""
import os
import signal
import time
import traceback

from eventlet import greenthread

from openstack.common import cfg
from openstack.common.gettextutils import _
from openstack.common import log as logging
from openstack.common import service
from tests import utils


LOG = logging.getLogger(__name__)


class ExtendedService(service.Service):
    def test_method(self):
        return 'service'


class ServiceManagerTestCase(utils.BaseTestCase):
    """Test cases for Services"""
    def test_override_manager_method(self):
        serv = ExtendedService()
        serv.start()
        self.assertEqual(serv.test_method(), 'service')


class ServiceWithTimer(service.Service):
    def start(self):
        super(ServiceWithTimer, self).start()
        self.timer_fired = 0
        self.tg.add_timer(1, self.timer_expired)

    def timer_expired(self):
        self.timer_fired = self.timer_fired + 1


class ServiceLauncherTest(utils.BaseTestCase):
    """
    Originally from nova/tests/integrated/test_multiprocess_api.py
    """

    def _spawn(self):
        self.workers = 2
        pid = os.fork()
        if pid == 0:
            # NOTE(johannes): We can't let the child processes exit back
            # into the unit test framework since then we'll have multiple
            # processes running the same tests (and possibly forking more
            # processes that end up in the same situation). So we need
            # to catch all exceptions and make sure nothing leaks out, in
            # particlar SystemExit, which is raised by sys.exit(). We use
            # os._exit() which doesn't have this problem.
            status = 0
            try:
                launcher = service.ProcessLauncher()
                serv = ServiceWithTimer()
                launcher.launch_service(serv, workers=self.workers)
                launcher.wait()
            except SystemExit as exc:
                status = exc.code
            except BaseException:
                # We need to be defensive here too
                try:
                    traceback.print_exc()
                except BaseException:
                    print "Couldn't print traceback"
                status = 2

            # Really exit
            os._exit(status)

        self.pid = pid

        # Wait for up to a second for workers to get started
        start = time.time()
        while time.time() - start < 1:
            workers = self._get_workers()
            if len(workers) == self.workers:
                break

            time.sleep(.1)

        self.assertEqual(len(workers), self.workers)
        return workers

    def tearDown(self):
        if self.pid:
            # Make sure all processes are stopped
            os.kill(self.pid, signal.SIGTERM)

            # Make sure we reap our test process
            self._reap_test()

        super(ServiceLauncherTest, self).tearDown()

    def _reap_test(self):
        pid, status = os.waitpid(self.pid, 0)
        self.pid = None
        return status

    def _get_workers(self):
        f = os.popen('ps ax -o pid,ppid,command')
        # Skip ps header
        f.readline()

        processes = [tuple(int(p) for p in l.strip().split()[:2])
                     for l in f.readlines()]
        return [p for p, pp in processes if pp == self.pid]

    def test_killed_worker_recover(self):
        start_workers = self._spawn()

        # kill one worker and check if new worker can come up
        LOG.info('pid of first child is %s' % start_workers[0])
        os.kill(start_workers[0], signal.SIGTERM)

        # loop and check if new worker is spawned (for 1 second max)
        start = time.time()
        while time.time() - start < 1:
            end_workers = self._get_workers()
            LOG.info('workers: %r' % end_workers)

            if start_workers != end_workers:
                break

            time.sleep(.1)

        # Make sure worker pids don't match
        self.assertNotEqual(start_workers, end_workers)

    def _terminate_with_signal(self, sig):
        self._spawn()

        os.kill(self.pid, sig)

        # loop and check if all processes are killed (for 1 second max)
        start = time.time()
        while time.time() - start < 1:
            workers = self._get_workers()
            LOG.info('workers: %r' % workers)

            if not workers:
                break

            time.sleep(.1)

        self.assertFalse(workers, 'No OS processes left.')

    def test_terminate_sigkill(self):
        self._terminate_with_signal(signal.SIGKILL)
        status = self._reap_test()
        self.assertTrue(os.WIFSIGNALED(status))
        self.assertEqual(os.WTERMSIG(status), signal.SIGKILL)

    def test_terminate_sigterm(self):
        self._terminate_with_signal(signal.SIGTERM)
        status = self._reap_test()
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)
