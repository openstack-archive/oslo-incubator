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

import abc
import errno
import multiprocessing
import os
import signal
import socket
import time
import traceback

import eventlet
from eventlet import event
import mock
from oslotest import base as test_base
from oslotest import moxstubout
import six
from six.moves import mox

from openstack.common import eventlet_backdoor
from openstack.common.fixture import config
from openstack.common import log as logging
from openstack.common.notifier import api as notifier_api
from openstack.common import service


LOG = logging.getLogger(__name__)


def _wait(predicate, timeout, fail=False):
    """Wait until predicate return True, will give up after timeout
    raising AssertionError in case fail was set to True.
    """
    start = time.time()
    while not predicate():
        if time.time() - start > timeout:
            if fail:
                raise AssertionError('Predicate never succeeded')
            break
        time.sleep(.1)


class ExtendedService(service.Service):
    def test_method(self):
        return 'service'


class ServiceManagerTestCase(test_base.BaseTestCase):
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


@six.add_metaclass(abc.ABCMeta)
class SubProcess(object):
    """Abstract class for creating and managing custom sub process."""

    def __init__(self):
        self._status = None  # Exit status.
        self._pid = None
        self._spawn()

    @property
    def status(self):
        """Block waiting for subprocess exit status."""
        if self._status is None:
            pid, status = os.waitpid(self._pid, 0)
            if pid:  # Process finished.
                self._pid = None
                self._status = status
        return self._status

    def _spawn(self):
        self._pid = os.fork()
        if self._pid == 0:
            os.setsid()
            status = self.child_callback()
            # Really exit
            os._exit(status)

        self.parent_callback()

    def kill(self, sig=signal.SIGTERM):
        """Send a signal to subprocess, default to send SIGTERN."""
        if self._pid:
            # Make sure all processes are stopped
            os.kill(self._pid, sig)

    @abc.abstractmethod
    def child_callback(self):
        """Abstract method to execute in the subprocess after fork,
        the subprocess exit status will be whatever this method return.
        """

    def parent_callback(self):
        """Method to execute in the parent process after fork."""


@six.add_metaclass(abc.ABCMeta)
class ServiceTestBase(test_base.BaseTestCase):
    """A base class for ServiceLauncherTest and ServiceRestartTest."""

    def setUp(self):
        super(ServiceTestBase, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        # FIXME(markmc): Ugly hack to workaround bug #1073732
        self.CONF.unregister_opts(notifier_api.notifier_opts)
        # NOTE(markmc): ConfigOpts.log_opt_values() uses CONF.config-file
        self.CONF(args=[], default_config_files=[])
        self.addCleanup(self.CONF.reset)
        self.addCleanup(self.CONF.register_opts, notifier_api.notifier_opts)

        self.launcher = self.Launcher()
        self.addCleanup(self.launcher.kill)

    @abc.abstractproperty
    def Launcher(self):
        """Abstract property (or class variable) that should implement
        the SubProcess interface.
        """


class ServiceLauncherTest(ServiceTestBase):
    """Originally from nova/tests/integrated/test_multiprocess_api.py."""

    class Launcher(SubProcess):

        children_count = 2

        @property
        def workers(self):
            f = os.popen('ps ax -o pid,ppid,command')
            # Skip ps header
            f.readline()

            processes = [tuple(int(p) for p in l.strip().split()[:2])
                         for l in f]
            return [p for p, pp in processes if pp == self._pid]

        def child_callback(self):
            # NOTE(johannes): We can't let the child processes exit back
            # into the unit test framework since then we'll have multiple
            # processes running the same tests (and possibly forking more
            # processes that end up in the same situation). So we need
            # to catch all exceptions and make sure nothing leaks out, in
            # particular SystemExit, which is raised by sys.exit(). We use
            # os._exit() which doesn't have this problem.
            status = 0
            try:
                launcher = service.ProcessLauncher()
                serv = ServiceWithTimer()
                launcher.launch_service(serv, workers=self.children_count)
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
            return status

        def parent_callback(self):
            _wait(lambda: len(self.workers) == self.children_count,
                  10, fail=True)

    def test_killed_worker_recover(self):
        start_workers = self.launcher.workers

        # kill one worker and check if new worker can come up
        LOG.info('pid of first child is %s' % start_workers[0])
        os.kill(start_workers[0], signal.SIGTERM)

        # Wait at most 5 seconds to respawn a worker
        cond = lambda: start_workers != self.launcher.workers
        timeout = 5
        _wait(cond, timeout)

        # Make sure worker pids don't match
        end_workers = self.launcher.workers
        LOG.info('workers: %r' % end_workers)
        self.assertNotEqual(start_workers, end_workers)

    def _terminate_with_signal(self, sig):
        self.launcher.kill(sig)

        # Wait at most 5 seconds to kill all workers
        cond = lambda: not self.launcher.workers
        timeout = 5
        _wait(cond, timeout)

        workers = self.launcher.workers
        LOG.info('workers: %r' % workers)
        self.assertFalse(workers, 'No OS processes left.')

    def test_terminate_sigkill(self):
        self._terminate_with_signal(signal.SIGKILL)
        status = self.launcher.status
        self.assertTrue(os.WIFSIGNALED(status))
        self.assertEqual(os.WTERMSIG(status), signal.SIGKILL)

    def test_terminate_sigterm(self):
        self._terminate_with_signal(signal.SIGTERM)
        status = self.launcher.status
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)

    def test_child_signal_sighup(self):
        start_workers = self.launcher.workers

        os.kill(start_workers[0], signal.SIGHUP)
        # Wait at most 5 seconds to respawn a worker
        cond = lambda: start_workers == self.launcher.workers
        timeout = 5
        _wait(cond, timeout)

        # Make sure worker pids match
        end_workers = self.launcher.workers
        LOG.info('workers: %r' % end_workers)
        self.assertEqual(start_workers, end_workers)

    def test_parent_signal_sighup(self):
        start_workers = self.launcher.workers

        self.launcher.kill(signal.SIGHUP)
        # Wait at most 5 seconds to respawn a worker
        cond = lambda: start_workers == self.launcher.workers
        timeout = 5
        _wait(cond, timeout)

        # Make sure worker pids match
        end_workers = self.launcher.workers
        LOG.info('workers: %r' % end_workers)
        self.assertEqual(start_workers, end_workers)


class MultiProcessLauncherTest(ServiceLauncherTest):
    """Test case that launch multiple ProcessLauncher service."""

    class Launcher(ServiceLauncherTest.Launcher):
        """Class that launch multiple ProcessLauncher in the same
        subprocess, each in it's own greenlet.
        """

        launcher_count = 2
        # NOTE(Mouad): The biggest the number of children the easiest it's
        # to catch bugs like #1364876.
        children_count = 10

        def __init__(self):
            self.pool = eventlet.greenpool.GreenPool(self.launcher_count)
            super(self.__class__, self).__init__()

        def child_callback(self):
            status = 0
            try:
                for _ in range(self.launcher_count):
                    launcher = service.ProcessLauncher()
                    serv = ServiceWithTimer()
                    launcher.launch_service(serv, workers=self.children_count)
                    self.pool.spawn(launcher.wait)
                self.pool.waitall()
            except SystemExit as exc:
                status = exc.code
            return status

        def parent_callback(self):
            subprocess_count = self.launcher_count * self.children_count
            _wait(lambda: len(self.workers) == subprocess_count, 20, fail=True)


class ServiceRestartTest(ServiceTestBase):

    class Launcher(SubProcess):

        def __init__(self):
            self.ready = multiprocessing.Event()
            super(self.__class__, self).__init__()

        def child_callback(self):
            status = 0
            try:
                serv = ServiceWithTimer()
                launcher = service.ServiceLauncher()
                launcher.launch_service(serv)
                launcher.wait(ready_callback=self.ready.set)
            except SystemExit as exc:
                status = exc.code
            return status

    def test_service_restart(self):
        timeout = 5
        self.launcher.ready.wait(timeout)
        self.assertTrue(
            self.launcher.ready.is_set(), 'Service never became ready')
        self.launcher.ready.clear()

        self.launcher.kill(signal.SIGHUP)
        self.launcher.ready.wait(timeout)
        self.assertTrue(
            self.launcher.ready.is_set(), 'Service never back after SIGHUP')

    def test_terminate_sigterm(self):
        timeout = 5
        self.launcher.ready.wait(timeout)
        self.assertTrue(
            self.launcher.ready.is_set(), 'Service never became ready')

        self.launcher.kill(signal.SIGTERM)
        status = self.launcher.status
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


class LauncherTest(test_base.BaseTestCase):

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

    @mock.patch('openstack.common.service.ServiceLauncher.launch_service')
    def _test_launch_single(self, workers, mock_launch):
        svc = service.Service()
        service.launch(svc, workers=workers)
        mock_launch.assert_called_with(svc)

    def test_launch_none(self):
        self._test_launch_single(None)

    def test_launch_one_worker(self):
        self._test_launch_single(1)

    @mock.patch('openstack.common.service.ProcessLauncher.launch_service')
    def test_multiple_worker(self, mock_launch):
        svc = service.Service()
        service.launch(svc, workers=3)
        mock_launch.assert_called_with(svc, workers=3)


class ProcessLauncherTest(test_base.BaseTestCase):

    def test_stop(self):
        launcher = service.ProcessLauncher()
        self.assertTrue(launcher.running)

        launcher.children = [22, 222]
        with mock.patch('openstack.common.service.os.kill') as mock_kill:
            with mock.patch.object(launcher, '_wait_child') as _wait_child:
                _wait_child.side_effect = lambda: launcher.children.pop()
                launcher.stop()

        self.assertFalse(launcher.running)
        self.assertFalse(launcher.children)
        self.assertEqual([mock.call(22, signal.SIGTERM),
                          mock.call(222, signal.SIGTERM)],
                         mock_kill.mock_calls)
