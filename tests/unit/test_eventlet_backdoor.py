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
Unit Tests for eventlet backdoor
"""
from __future__ import print_function

import errno
import eventlet
import socket

from openstack.common import eventlet_backdoor
from openstack.common import log as logging
from tests import utils

LOG = logging.getLogger(__name__)


class BackdoorPortTest(utils.BaseTestCase):

    class MySock():
        def __init__(self, port):
            self.port = port

        def getsockname(self):
            return (None, self.port)

    def my_eventlet_spawn_n(self, server, *args, **kwargs):
        return None

    def common_backdoor_port_setup(self):
        self.mox.StubOutWithMock(eventlet, 'listen')
        self.stubs.Set(eventlet, 'spawn_n', self.my_eventlet_spawn_n)

    def test_backdoor_port(self):
        self.port_to_test = 1234
        self.config(backdoor_port=self.port_to_test)
        self.common_backdoor_port_setup()
        eventlet.listen(('localhost', self.port_to_test)).AndReturn(
            self.MySock(self.port_to_test))
        self.mox.ReplayAll()
        port = eventlet_backdoor.initialize_if_enabled()
        self.assertEqual(self.port_to_test, port)
        self.addCleanup(self.stubs.UnsetAll)

    def test_backdoor_port_inuse(self):
        self.port_to_test = 2345
        self.config(backdoor_port=self.port_to_test)
        self.common_backdoor_port_setup()
        eventlet.listen(('localhost', self.port_to_test)).AndRaise(
            socket.error(errno.EADDRINUSE, ''))
        self.mox.ReplayAll()
        self.assertRaises(socket.error,
                          eventlet_backdoor.initialize_if_enabled)
        self.addCleanup(self.stubs.UnsetAll)

    def test_backdoor_port_range(self):
        self.port_to_test = 8800
        self.config(backdoor_port='8800:8899')
        self.common_backdoor_port_setup()
        eventlet.listen(('localhost', self.port_to_test)).AndReturn(
            self.MySock(self.port_to_test))
        self.mox.ReplayAll()
        port = eventlet_backdoor.initialize_if_enabled()
        self.assertEqual(self.port_to_test, port)
        self.addCleanup(self.stubs.UnsetAll)

    def test_backdoor_port_range_all_inuse(self):
        self.port_to_test = 8800
        self.config(backdoor_port='8800:8899')
        self.common_backdoor_port_setup()
        for i in range(100):
            eventlet.listen(('localhost', self.port_to_test)).AndRaise(
                socket.error(errno.EADDRINUSE, ''))
            self.port_to_test += 1
        self.mox.ReplayAll()
        self.assertRaises(socket.error,
                          eventlet_backdoor.initialize_if_enabled)
        self.addCleanup(self.stubs.UnsetAll)

    def test_backdoor_port_range_one_inuse(self):
        self.port_to_test = 8800
        self.config(backdoor_port='8800:8899')
        self.common_backdoor_port_setup()
        eventlet.listen(('localhost', self.port_to_test)).AndRaise(
            socket.error(errno.EADDRINUSE, ''))
        self.port_to_test += 1
        eventlet.listen(('localhost', self.port_to_test)).AndReturn(
            self.MySock(self.port_to_test))
        self.mox.ReplayAll()
        port = eventlet_backdoor.initialize_if_enabled()
        self.assertEqual(self.port_to_test, port)
        self.addCleanup(self.stubs.UnsetAll)

    def test_backdoor_port_bad(self):
        self.config(backdoor_port='abc')
        self.assertRaises(eventlet_backdoor.EventletBackdoorConfigValueError,
                          eventlet_backdoor.initialize_if_enabled)
