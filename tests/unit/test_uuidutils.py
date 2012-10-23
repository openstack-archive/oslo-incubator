# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012 Intel Corporation.
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

import unittest
import uuid

import mox

from openstack.common import uuidutils


class UUIDUtilsTest(unittest.TestCase):

    def setUp(self):
        self.mox = mox.Mox()
        self.uuid = uuid.uuid4()

    def tearDown(self):
        self.mox.UnsetStubs()

    def test_uuid4(self):
        self.mox.StubOutWithMock(uuid, 'uuid4')
        uuid.uuid4().AndReturn(self.uuid)
        uuid.uuid4().AndReturn(self.uuid)
        self.mox.ReplayAll()

        expect = uuid.uuid4()
        actual = uuidutils.uuid4()
        self.mox.VerifyAll()

        self.assertEqual(expect, actual)

    def test_uuid4_hex(self):
        self.mox.StubOutWithMock(uuid, 'uuid4')
        uuid.uuid4().AndReturn(self.uuid)
        uuid.uuid4().AndReturn(self.uuid)
        self.mox.ReplayAll()

        expect = uuid.uuid4().hex
        actual = uuidutils.uuid4_hex()
        self.mox.VerifyAll()

        self.assertEqual(expect, actual)

    def test_uuid4_str(self):
        self.mox.StubOutWithMock(uuid, 'uuid4')
        uuid.uuid4().AndReturn(self.uuid)
        uuid.uuid4().AndReturn(self.uuid)
        self.mox.ReplayAll()

        expect = str(uuid.uuid4())
        actual = uuidutils.uuid4_str()
        self.mox.VerifyAll()

        self.assertEqual(expect, actual)

    def test_uuid4_randint(self):
        val = uuidutils.uuid4_randint()
        self.assertTrue(isinstance(val, long))

    def test_is_uuid_like(self):
        self.assertTrue(uuidutils.is_uuid_like(str(uuid.uuid4())))

    def test_is_uuid_like_id(self):
        self.assertFalse(uuidutils.is_uuid_like(1234567))

    def test_is_uuid_like_name(self):
        self.assertFalse(uuidutils.is_uuid_like('zhongyueluo'))
