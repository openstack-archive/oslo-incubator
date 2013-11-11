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

import uuid

from openstack.common import test
from openstack.common import uuidutils


class UUIDUtilsTest(test.BaseTestCase):

    def test_generate_uuid(self):
        uuid_string = uuidutils.generate_uuid()
        self.assertTrue(isinstance(uuid_string, str))
        self.assertEqual(len(uuid_string), 36)
        # make sure there are 4 dashes
        self.assertEqual(len(uuid_string.replace('-', '')), 32)

    def test_generate_pure_uuid(self):
        pure_uuid = uuidutils.generate_pure_uuid()
        self.assertTrue(isinstance(pure_uuid, uuid.UUID))
        self.assertEqual(len(str(pure_uuid)), 36)
        # make sure there are 4 dashes
        self.assertEqual(len(str(pure_uuid).replace('-', '')), 32)

    def test_is_uuid_like(self):
        self.assertTrue(uuidutils.is_uuid_like(str(uuid.uuid4())))

    def test_id_is_uuid_like(self):
        self.assertFalse(uuidutils.is_uuid_like(1234567))

    def test_name_is_uuid_like(self):
        self.assertFalse(uuidutils.is_uuid_like('zhongyueluo'))
