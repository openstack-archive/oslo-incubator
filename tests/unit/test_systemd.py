# Copyright 2014 Red Hat, Inc.
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
import socket

from oslotest import base as test_base
from oslotest import moxstubout

from openstack.common import systemd


class SystemdTestCase(test_base.BaseTestCase):
    """Test case for Systemd service readiness."""
    def setUp(self):
        super(SystemdTestCase, self).setUp()
        self.mox = self.useFixture(moxstubout.MoxStubout()).mox
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs

    def test_sd_notify(self):
        self.ready = False

        def mock_getenv(key):
            return '@fake_socket'

        def mock_socket(cls, *args):

            class FakeSocket():
                def connect(fs, socket):
                    pass

                def close(fs):
                    pass

                def sendall(fs, data):
                    if (data == 'READY=1'):
                        self.ready = True

            return FakeSocket()

        self.stubs.Set(os, 'getenv', mock_getenv)
        self.stubs.Set(socket, 'socket', mock_socket)

        systemd.notify()

        self.assertEqual(self.ready, True)
