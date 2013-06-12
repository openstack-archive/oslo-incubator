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
import errno
import socket

import eventlet
try:
    from mox3 import mox
except ImportError:
    import mox

from openstack.common import eventlet_backdoor
from openstack.common.fixture import config
from openstack.common.fixture import moxstubout
from openstack.common import test


class BackdoorPortTest(test.BaseTestCase):

    def setUp(self):
        super(BackdoorPortTest, self).setUp()
        self.mox = self.useFixture(moxstubout.MoxStubout()).mox
        self.config = self.useFixture(config.Config()).config

    def common_backdoor_port_setup(self):
        self.sock = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(eventlet, 'listen')
        self.mox.StubOutWithMock(eventlet, 'spawn_n')

    def test_backdoor_port_inuse(self):
        self.config(backdoor_port=2345)
        self.common_backdoor_port_setup()
        eventlet.listen(('localhost', 2345)).AndRaise(
            socket.error(errno.EADDRINUSE, ''))
        self.mox.ReplayAll()
        self.assertRaises(socket.error,
                          eventlet_backdoor.initialize_if_enabled)

    def test_backdoor_port_range(self):
        self.config(backdoor_port='8800:8899')
        self.common_backdoor_port_setup()
        eventlet.listen(('localhost', 8800)).AndReturn(self.sock)
        self.sock.getsockname().AndReturn(('127.0.0.1', 8800))
        eventlet.spawn_n(eventlet.backdoor.backdoor_server, self.sock,
                         locals=mox.IsA(dict))
        self.mox.ReplayAll()
        port = eventlet_backdoor.initialize_if_enabled()
        self.assertEqual(port, 8800)

    def test_backdoor_port_range_all_inuse(self):
        self.config(backdoor_port='8800:8899')
        self.common_backdoor_port_setup()
        for i in range(8800, 8900):
            eventlet.listen(('localhost', i)).AndRaise(
                socket.error(errno.EADDRINUSE, ''))
        self.mox.ReplayAll()
        self.assertRaises(socket.error,
                          eventlet_backdoor.initialize_if_enabled)

    def test_backdoor_port_bad(self):
        self.config(backdoor_port='abc')
        self.assertRaises(eventlet_backdoor.EventletBackdoorConfigValueError,
                          eventlet_backdoor.initialize_if_enabled)
