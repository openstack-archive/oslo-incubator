# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 IBM
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

import unittest

from openstack.common.rpc import common as rpc_common
from openstack.common.rpc import dispatcher
from openstack.common.rpc import proxy


class RpcTestProxy(proxy.RpcProxy):
    def does_exist(self, *args):
        pass


class RpcMissingMethodTestCase(unittest.TestCase):
    def setUp(self):
        _proxy = RpcTestProxy("MethodTest", "1.0")
        self._dispatcher = dispatcher.RpcDispatcher([_proxy])

    def test_present_method_match(self):
        self._dispatcher.dispatch(None, "1.0", "does_exist")

    def test_present_method_no_match(self):
        self.assertRaises(rpc_common.UnsupportedRpcVersion,
                          self._dispatcher.dispatch,
                          None, "2.0", "does_exist")

    def test_absent_method_match(self):
        self.assertRaises(AttributeError,
                          self._dispatcher.dispatch,
                          None, "1.0", "does_not_exist")

    def test_absent_method_no_match(self):
        self.assertRaises(rpc_common.UnsupportedRpcVersion,
                          self._dispatcher.dispatch,
                          None, "2.0", "does_not_exist")
