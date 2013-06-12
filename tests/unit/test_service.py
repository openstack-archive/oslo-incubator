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
Unit Tests for service class
"""

from __future__ import print_function

import errno
import multiprocessing
import os
import signal
import socket
import time
import traceback

import eventlet
from eventlet import event
from six.moves import mox

from openstack.common import eventlet_backdoor
from openstack.common.fixture import config
from openstack.common.fixture import moxstubout
from openstack.common import log as logging
from openstack.common.notifier import api as notifier_api
from openstack.common import service
from openstack.common import test


LOG = logging.getLogger(__name__)


class ExtendedService(service.Service):
    def test_method(self):
        return 'service'


class ServiceManagerTestCase(test.BaseTestCase):
    """Test cases for Services."""
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


class ServiceTestBase(test.BaseTestCase):
    """A base class for ServiceLauncherTest and ServiceRestartTest."""

    def _wait(self, cond, timeout):
        start = time.time()
        while not cond():
            if time.time() - start > timeout:
                break
            time.sleep(.1)

    def setUp(self):
        super(ServiceTestBase, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        # FIXME(markmc): Ugly hack to workaround bug #1073732
        self.CONF.unregister_opts(notifier_api.notifier_opts)
        # NOTE(markmc): ConfigOpts.log_opt_values() uses CONF.config-file
        self.CONF(args=[], default_config_files=[])
        self.addCleanup(self.CONF.reset)
        self.addCleanup(self.CONF.register_opts, notifier_api.notifier_opts)
        self.addCleanup(self._reap_pid)

    def _reap_pid(self):
        if self.pid:
            # Make sure all processes are stopped
            os.kill(self.pid, signal.SIGTERM)

            # Make sure we reap our test process
            self._reap_test()

    def _reap_test(self):
        pid, status = os.waitpid(self.pid, 0)
        self.pid = None
        return status


class ServiceLauncherTest(ServiceTestBase):
    """Originally from nova/tests/integrated/test_multiprocess_api.py."""

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
                    print("Couldn't print traceback")
                status = 2

            # Really exit
            os._exit(status)

        self.pid = pid

        # Wait at most 10 seconds to spawn workers
        cond = lambda: self.workers == len(self._get_workers())
        timeout = 10
        self._wait(cond, timeout)

        workers = self._get_workers()
        self.assertEqual(len(workers), self.workers)
        return workers

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

        # Wait at most 5 seconds to respawn a worker
        cond = lambda: start_workers != self._get_workers()
        timeout = 5
        self._wait(cond, timeout)

        # Make sure worker pids don't match
        end_workers = self._get_workers()
        LOG.info('workers: %r' % end_workers)
        self.assertNotEqual(start_workers, end_workers)

    def _terminate_with_signal(self, sig):
        self._spawn()

        os.kill(self.pid, sig)

        # Wait at most 5 seconds to kill all workers
        cond = lambda: not self._get_workers()
        timeout = 5
        self._wait(cond, timeout)

        workers = self._get_workers()
        LOG.info('workers: %r' % workers)
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

    def test_child_signal_sighup(self):
        start_workers = self._spawn()

        os.kill(start_workers[0], signal.SIGHUP)
        # Wait at most 5 seconds to respawn a worker
        cond = lambda: start_workers == self._get_workers()
        timeout = 5
        self._wait(cond, timeout)

        # Make sure worker pids match
        end_workers = self._get_workers()
        LOG.info('workers: %r' % end_workers)
        self.assertEqual(start_workers, end_workers)

    def test_parent_signal_sighup(self):
        start_workers = self._spawn()

        os.kill(self.pid, signal.SIGHUP)
        # Wait at most 5 seconds to respawn a worker
        cond = lambda: start_workers == self._get_workers()
        timeout = 5
        self._wait(cond, timeout)

        # Make sure worker pids match
        end_workers = self._get_workers()
        LOG.info('workers: %r' % end_workers)
        self.assertEqual(start_workers, end_workers)


class ServiceRestartTest(ServiceTestBase):

    def _spawn_service(self):
        ready_event = multiprocessing.Event()
        pid = os.fork()
        status = 0
        if pid == 0:
            try:
                serv = ServiceWithTimer()
                launcher = service.ServiceLauncher()
                launcher.launch_service(serv)
                launcher.wait(ready_callback=ready_event.set)
            except SystemExit as exc:
                status = exc.code
            os._exit(status)
        self.pid = pid
        return ready_event

    def test_service_restart(self):
        ready = self._spawn_service()

        timeout = 5
        ready.wait(timeout)
        self.assertTrue(ready.is_set(), 'Service never became ready')
        ready.clear()

        os.kill(self.pid, signal.SIGHUP)
        ready.wait(timeout)
        self.assertTrue(ready.is_set(), 'Service never back after SIGHUP')

    def test_terminate_sigterm(self):
        ready = self._spawn_service()
        timeout = 5
        ready.wait(timeout)
        self.assertTrue(ready.is_set(), 'Service never became ready')

        os.kill(self.pid, signal.SIGTERM)

        status = self._reap_test()
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)


class _Service(service.Service):
    def __init__(self):
        super(_Service, self).__init__()
        self.init = event.Event()
        self.cleaned_up = False

    def start(self):
        self.init.send()

    def stop(self):
        self.cleaned_up = True
        super(_Service, self).stop()


class LauncherTest(test.BaseTestCase):

    def setUp(self):
        super(LauncherTest, self).setUp()
        self.mox = self.useFixture(moxstubout.MoxStubout()).mox
        self.config = self.useFixture(config.Config()).config

    def test_backdoor_port(self):
        self.config(backdoor_port='1234')

        sock = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(eventlet, 'listen')
        self.mox.StubOutWithMock(eventlet, 'spawn_n')

        eventlet.listen(('localhost', 1234)).AndReturn(sock)
        sock.getsockname().AndReturn(('127.0.0.1', 1234))
        eventlet.spawn_n(eventlet.backdoor.backdoor_server, sock,
                         locals=mox.IsA(dict))

        self.mox.ReplayAll()

        svc = service.Service()
        launcher = service.launch(svc)
        self.assertEqual(svc.backdoor_port, 1234)
        launcher.stop()

    def test_backdoor_inuse(self):
        sock = eventlet.listen(('localhost', 0))
        port = sock.getsockname()[1]
        self.config(backdoor_port=port)
        svc = service.Service()
        self.assertRaises(socket.error,
                          service.launch, svc)
        sock.close()

    def test_backdoor_port_range_one_inuse(self):
        self.config(backdoor_port='8800:8900')

        sock = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(eventlet, 'listen')
        self.mox.StubOutWithMock(eventlet, 'spawn_n')

        eventlet.listen(('localhost', 8800)).AndRaise(
            socket.error(errno.EADDRINUSE, ''))
        eventlet.listen(('localhost', 8801)).AndReturn(sock)
        sock.getsockname().AndReturn(('127.0.0.1', 8801))
        eventlet.spawn_n(eventlet.backdoor.backdoor_server, sock,
                         locals=mox.IsA(dict))

        self.mox.ReplayAll()

        svc = service.Service()
        launcher = service.launch(svc)
        self.assertEqual(svc.backdoor_port, 8801)
        launcher.stop()

    def test_backdoor_port_reverse_range(self):
        # backdoor port should get passed to the service being launched
        self.config(backdoor_port='8888:7777')
        svc = service.Service()
        self.assertRaises(eventlet_backdoor.EventletBackdoorConfigValueError,
                          service.launch, svc)

    def test_graceful_shutdown(self):
        # test that services are given a chance to clean up:
        svc = _Service()

        launcher = service.launch(svc)
        # wait on 'init' so we know the service had time to start:
        svc.init.wait()

        launcher.stop()
        self.assertTrue(svc.cleaned_up)
        self.assertTrue(svc._done.ready())

        # make sure stop can be called more than once.  (i.e. play nice with
        # unit test fixtures in nova bug #1199315)
        launcher.stop()
