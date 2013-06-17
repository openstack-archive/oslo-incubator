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

from __future__ import print_function

import errno
import eventlet
import os
import signal
import socket
import sys
import time
import traceback

from oslo.config import cfg

from openstack.common import eventlet_backdoor
from openstack.common import log as logging
from openstack.common.notifier import api as notifier_api
from openstack.common import service
from tests import utils

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class ExtendedService(service.Service):
    def test_method(self):
        return 'service'


class ServiceManagerTestCase(utils.BaseTestCase):
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


class ServiceLauncherTest(utils.BaseTestCase):
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

    def _wait(self, cond, timeout):
        start = time.time()
        while True:
            if cond():
                break
            if time.time() - start > timeout:
                break
            time.sleep(.1)

    def setUp(self):
        super(ServiceLauncherTest, self).setUp()
        # FIXME(markmc): Ugly hack to workaround bug #1073732
        CONF.unregister_opts(notifier_api.notifier_opts)
        # NOTE(markmc): ConfigOpts.log_opt_values() uses CONF.config-file
        CONF(args=[], default_config_files=[])
        self.addCleanup(CONF.reset)
        self.addCleanup(CONF.register_opts, notifier_api.notifier_opts)
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


class LauncherTest(utils.BaseTestCase):
    def test_backdoor_port(self):
        # backdoor port should get passed to the service being launched
        self.config(backdoor_port=1234)
        svc = service.Service()
        launcher = service.launch(svc)
        self.assertEqual(1234, svc.backdoor_port)
        launcher.stop()

    def test_backdoor_port_range(self):
        # backdoor port should get passed to the service being launched
        self.config(backdoor_port='8800:8899')
        svc1 = service.Service()
        launcher1 = service.launch(svc1)
        self.assertEqual(8800, svc1.backdoor_port)
        svc2 = service.Service()
        launcher2 = service.launch(svc2)
        self.assertEqual(8801, svc2.backdoor_port)
        launcher1.stop()
        launcher2.stop()

    def test_backdoor_port_negative_range(self):
        # for some reason this does not fail on python 2.6
        if sys.hexversion < 0x02070000:
            self.skipTest('python version less than 2.7')
        # backdoor port should get passed to the service being launched
        self.config(backdoor_port='-1:100')
        svc = service.Service()
        self.assertRaises(Exception, service.launch, svc)

    def test_backdoor_port_out_of_range(self):
        # for some reason this does not fail on python 2.6
        if sys.hexversion < 0x02070000:
            self.skipTest('python version less than 2.7')
        # backdoor port should get passed to the service being launched
        self.config(backdoor_port='65536:99999')
        svc = service.Service()
        self.assertRaises(Exception, service.launch, svc)

    def test_backdoor_port_reverse_range(self):
        # backdoor port should get passed to the service being launched
        self.config(backdoor_port='8888:7777')
        svc = service.Service()
        self.assertRaises(Exception, service.launch, svc)


class BackdoorPortTest(utils.BaseTestCase):

    class MySock():
        def __init__(self, port):
            self.port = port

        def getsockname(self):
            return (None, self.port)

    def my_eventlet_listen(self, addr):
        host, port = addr
        self.eventlet_listen_calls += 1
        if self.listen_action == 'in use exception':
            raise socket.error(errno.EADDRINUSE,
                               errno.errorcode[errno.EADDRINUSE])
        if (self.listen_action == 'in use exception then suceed' and
           self.eventlet_listen_calls == 1):
            raise socket.error(errno.EADDRINUSE,
                               errno.errorcode[errno.EADDRINUSE])
        return self.MySock(port)

    def my_eventlet_spawn_n(self, server, *args, **kwargs):
        return None

    def my_info_logger(self, msg, *args, **kwargs):
        self.info_logger_calls += 1
        self.assertTrue('Eventlet backdoor listening on' in msg)
        self.orig_info_logger(msg, *args, **kwargs)

    def common_backdoor_port_setup(self):
        self.stubs.Set(eventlet, 'listen', self.my_eventlet_listen)
        self.stubs.Set(eventlet, 'spawn_n', self.my_eventlet_spawn_n)
        self.orig_info_logger = eventlet_backdoor.LOG.info
        self.stubs.Set(eventlet_backdoor.LOG, 'info', self.my_info_logger)
        self.info_logger_calls = 0
        self.eventlet_listen_calls = 0

    def test_backdoor_port(self):
        self.port_to_test = 1234
        self.config(backdoor_port=self.port_to_test)
        self.listen_action = 'succeed'
        self.common_backdoor_port_setup()
        port = eventlet_backdoor.initialize_if_enabled()
        self.assertEqual(self.info_logger_calls, 1)
        self.assertEqual(self.eventlet_listen_calls, 1)
        self.assertEqual(self.port_to_test, port)
        self.stubs.UnsetAll()

    def test_backdoor_port_inuse(self):
        self.port_to_test = 2345
        self.config(backdoor_port=self.port_to_test)
        self.listen_action = 'in use exception'
        self.common_backdoor_port_setup()
        self.assertRaises(socket.error,
                          eventlet_backdoor.initialize_if_enabled)
        self.assertEqual(self.info_logger_calls, 0)
        self.assertEqual(self.eventlet_listen_calls, 1)
        self.stubs.UnsetAll()

    def test_backdoor_port_range(self):
        self.port_to_test = 8800
        self.config(backdoor_port='8800:8899')
        self.listen_action = 'succeed'
        self.common_backdoor_port_setup()
        port = eventlet_backdoor.initialize_if_enabled()
        self.assertEqual(self.info_logger_calls, 1)
        self.assertEqual(self.eventlet_listen_calls, 1)
        self.assertEqual(self.port_to_test, port)
        self.stubs.UnsetAll()

    def test_backdoor_port_range_all_inuse(self):
        self.port_to_test = 8800
        self.config(backdoor_port='8800:8899')
        self.listen_action = 'in use exception'
        self.common_backdoor_port_setup()
        self.assertRaises(socket.error,
                          eventlet_backdoor.initialize_if_enabled)
        self.assertEqual(self.info_logger_calls, 0)
        self.assertEqual(self.eventlet_listen_calls, 100)
        self.stubs.UnsetAll()

    def test_backdoor_port_range_one_inuse(self):
        self.port_to_test = 8800
        self.config(backdoor_port='8800:8899')
        self.listen_action = 'in use exception then suceed'
        self.common_backdoor_port_setup()
        port = eventlet_backdoor.initialize_if_enabled()
        self.assertEqual(self.info_logger_calls, 1)
        self.assertEqual(self.eventlet_listen_calls, 2)
        self.assertEqual(self.port_to_test + 1, port)
        self.stubs.UnsetAll()

    def test_backdoor_port_bad(self):
        self.config(backdoor_port='abc')
        self.common_backdoor_port_setup()
        self.assertRaises(eventlet_backdoor.EventletBackdoorConfigValueError,
                          eventlet_backdoor.initialize_if_enabled)
        self.assertEqual(self.info_logger_calls, 0)
        self.assertEqual(self.eventlet_listen_calls, 0)
        self.stubs.UnsetAll()
