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
Unit Tests for remote procedure calls using fake_impl
"""

import eventlet
eventlet.monkey_patch()
from oslo.config import cfg

from openstack.common.rpc import impl_fake
from tests.unit.rpc import common


CONF = cfg.CONF


class RpcFakeTestCase(common.BaseRpcTestCase):

    rpc = impl_fake

    def test_non_primitive_raises(self):
        class Foo(object):
            pass

        self.assertRaises(TypeError, self.rpc.cast, CONF, self.context,
                          'foo', {'x': Foo()})
        self.assertRaises(TypeError, self.rpc.call, CONF, self.context,
                          'foo', {'x': Foo()})
