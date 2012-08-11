# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
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
import os
import sys

from eventlet import event
from eventlet import greenthread
from eventlet import greenpool

from openstack.common import loopingcall
from openstack.common.gettextutils import _
from openstack.common import log as logging


LOG = logging.getLogger(__name__)


def _thread_done(gt, *args, **kwargs):
    args[0].thread_done(args[1])


class Thread(object):
    """
    Wrapper around a greenthread, that holds a reference to
    the ThreadGroup. The Thread will notify the ThreadGroup
    when it has done so it can be removed from the threads
    list.
    """
    def __init__(self, name, thread, group):
        self.name = name
        self.thread = thread
        self.thread.link(_thread_done, group, self)

    def stop(self):
        self.thread.cancel()

    def wait(self):
        return self.thread.wait()


class ThreadGroup():
    """
    The point of this class is to:
    - keep track of timers and greenthreads (making it easier to stop them
      when need be).
    - provide an easy API to add timers.
    """
    def __init__(self, name, thread_pool_size=10):
        self.name = name
        self.pool = greenpool.GreenPool(thread_pool_size)
        self.threads = []
        self.timers = []

    def add_timer(self, interval, callback, initial_delay=None,
                  *args, **kwargs):
        pulse = loopingcall.LoopingCall(callback, *args, **kwargs)
        pulse.start(interval=interval,
                    initial_delay=initial_delay)
        self.timers.append(pulse)

    def add_thread(self, callback, *args, **kwargs):
        gt = self.pool.spawn(callback, *args, **kwargs)
        th = Thread(callback.__name__, gt, self)
        self.threads.append(th)

    def thread_done(self, thread):
        try:
            thread.wait()
        except Exception as ex:
            LOG.exception(ex)
        finally:
            self.threads.remove(thread)

    def stop(self):
        current = greenthread.getcurrent()
        for x in self.threads:
            if x is current:
                # don't kill the current thread.
                continue
            try:
                x.stop()
            except Exception as ex:
                LOG.exception(ex)

        for x in self.timers:
            try:
                x.stop()
            except Exception as ex:
                LOG.exception(ex)
        self.timers = []

    def wait(self):
        for x in self.timers:
            try:
                x.wait()
            except Exception as ex:
                LOG.exception(ex)
        current = greenthread.getcurrent()
        for x in self.threads:
            if x is current:
                continue
            try:
                x.wait()
            except Exception as ex:
                LOG.exception(ex)
