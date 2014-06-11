# Copyright 2011 OpenStack Foundation.
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

from oslotest import base as test_base

from openstack.common import context


class ContextTest(test_base.BaseTestCase):

    def test_context(self):
        ctx = context.RequestContext()
        self.assertTrue(ctx)

    def test_admin_context_show_deleted_flag_default(self):
        ctx = context.get_admin_context()
        self.assertFalse(ctx.show_deleted)

    def test_from_dict(self):
        dct = {
            "auth_token": "token1",
            "user": "user1",
            "tenant": "tenant1",
            "domain": "domain1",
            "user_domain": "user_domain1",
            "project_domain": "project_domain1",
            "is_admin": True,
            "read_only": True,
            "show_deleted": True,
            "request_id": "request1",
            "instance_uuid": "instance1",
            "extra_data": "foo"
        }
        ctx = context.RequestContext.from_dict(dct)
        self.assertEqual("token1", ctx.auth_token)
        self.assertEqual("user1", ctx.user)
        self.assertEqual("tenant1", ctx.tenant)
        self.assertEqual("domain1", ctx.domain)
        self.assertEqual("user_domain1", ctx.user_domain)
        self.assertEqual("project_domain1", ctx.project_domain)
        self.assertTrue(ctx.is_admin)
        self.assertTrue(ctx.read_only)
        self.assertTrue(ctx.show_deleted)
        self.assertEqual("request1", ctx.request_id)
        self.assertEqual("instance1", ctx.instance_uuid)
