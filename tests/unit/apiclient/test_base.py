# Copyright 2013 OpenStack Foundation
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

import mock

from openstack.common.apiclient import base
from openstack.common.apiclient import client
from openstack.common.apiclient import exceptions
from openstack.common.apiclient import fake_client
from openstack.common import test


class HumanResource(base.Resource):
    HUMAN_ID = True


class HumanResourceManager(base.ManagerWithFind):
    resource_class = HumanResource

    def list(self):
        return self._list("/human_resources", "human_resources")

    def get(self, human_resource):
        return self._get(
            "/human_resources/%s" % base.getid(human_resource),
            "human_resource")

    def update(self, human_resource, name):
        body = {
            "human_resource": {
                "name": name,
            },
        }
        return self._put(
            "/human_resources/%s" % base.getid(human_resource),
            body,
            "human_resource")


class CrudResource(base.Resource):
    pass


class CrudResourceManager(base.CrudManager):
    """Manager class for manipulating Identity crud_resources."""
    resource_class = CrudResource
    collection_key = 'crud_resources'
    key = 'crud_resource'

    def get(self, crud_resource):
        return super(CrudResourceManager, self).get(
            crud_resource_id=base.getid(crud_resource))


class FakeHTTPClient(fake_client.FakeHTTPClient):
    crud_resource_json = {"id": "1", "domain_id": "my-domain"}

    def get_human_resources(self, **kw):
        return (200, {}, {'human_resources': [
            {'id': 1, 'name': '256 MB Server'},
            {'id': 2, 'name': '512 MB Server'},
            {'id': 'aa1', 'name': '128 MB Server'}
        ]})

    def get_human_resources_1(self, **kw):
        res = self.get_human_resources()[2]['human_resources'][0]
        return (200, {}, {'human_resource': res})

    def put_human_resources_1(self, **kw):
        kw = kw["json"]["human_resource"].copy()
        kw["id"] = "1"
        return (200, {}, {'human_resource': kw})

    def post_crud_resources(self, **kw):
        return (200, {}, {"crud_resource": {"id": "1"}})

    def get_crud_resources(self, **kw):
        crud_resources = []
        if kw.get("domain_id") == self.crud_resource_json["domain_id"]:
            crud_resources = [self.crud_resource_json]
        else:
            crud_resources = []
        return (200, {}, {"crud_resources": crud_resources})

    def get_crud_resources_1(self, **kw):
        return (200, {}, {"crud_resource": self.crud_resource_json})

    def head_crud_resources_1(self, **kw):
        return (204, {}, None)

    def patch_crud_resources_1(self, **kw):
        self.crud_resource_json.update(kw)
        return (200, {}, {"crud_resource": self.crud_resource_json})

    def delete_crud_resources_1(self, **kw):
        return (202, {}, None)


class TestClient(client.BaseClient):

    service_type = "test"

    def __init__(self, http_client, extensions=None):
        super(TestClient, self).__init__(
            http_client, extensions=extensions)

        self.human_resources = HumanResourceManager(self)
        self.crud_resources = CrudResourceManager(self)


class ResourceTest(test.BaseTestCase):

    def test_resource_repr(self):
        r = base.Resource(None, dict(foo="bar", baz="spam"))
        self.assertEqual(repr(r), "<Resource baz=spam, foo=bar>")

    def test_getid(self):
        class TmpObject(base.Resource):
            id = "4"
        self.assertEqual(base.getid(TmpObject(None, {})), "4")

    def test_human_id(self):
        r = base.Resource(None, {"name": "1"})
        self.assertIsNone(r.human_id)
        r = HumanResource(None, {"name": "1"})
        self.assertEqual(r.human_id, "1")

    def test__loaded(self):
        client = TestClient(FakeHTTPClient())
        mgr = CrudResourceManager(client)
        r = base.Resource(mgr, {"id": 1})
        self.assertFalse(r.is_loaded)
        self.assertEqual("my-domain", r.domain_id)
        self.assertTrue(r.is_loaded)


class BaseManagerTest(test.BaseTestCase):

    def setUp(self):
        super(BaseManagerTest, self).setUp()
        self.http_client = FakeHTTPClient()
        self.tc = TestClient(self.http_client)

    def test_resource_lazy_getattr(self):
        f = HumanResource(self.tc.human_resources, {'id': 1})
        self.assertEqual(f.name, '256 MB Server')
        self.http_client.assert_called('GET', '/human_resources/1')

        # Missing stuff still fails after a second get
        self.assertRaises(AttributeError, getattr, f, 'blahblah')

    def test_eq(self):
        # Two resources of the same type with the same id: equal
        r1 = base.Resource(None, {'id': 1, 'name': 'hi'})
        r2 = base.Resource(None, {'id': 1, 'name': 'hello'})
        self.assertEqual(r1, r2)

        # Two resources of different types: never equal
        r1 = base.Resource(None, {'id': 1})
        r2 = HumanResource(None, {'id': 1})
        self.assertNotEqual(r1, r2)

        # Two resources with no ID: equal if their info is equal
        r1 = base.Resource(None, {'name': 'joe', 'age': 12})
        r2 = base.Resource(None, {'name': 'joe', 'age': 12})
        self.assertEqual(r1, r2)

    def test_findall_invalid_attribute(self):
        # Make sure findall with an invalid attribute doesn't cause errors.
        # The following should not raise an exception.
        self.tc.human_resources.findall(vegetable='carrot')

        # However, find() should raise an error
        self.assertRaises(exceptions.NotFound,
                          self.tc.human_resources.find,
                          vegetable='carrot')

    def test_update(self):
        name = "new-name"
        human_resource = self.tc.human_resources.update("1", name)
        self.assertEqual(human_resource.id, "1")
        self.assertEqual(human_resource.name, name)


class BaseManagerTestCase(test.BaseTestCase):

    def setUp(self):
        super(BaseManagerTestCase, self).setUp()

        self.response = mock.MagicMock()
        self.http_client = mock.MagicMock()
        self.http_client.get.return_value = self.response
        self.http_client.post.return_value = self.response

        self.manager = base.BaseManager(self.http_client)
        self.manager.resource_class = HumanResource

    def test_list(self):
        self.response.json.return_value = {'human_resources': [{'id': 42}]}
        expected = [HumanResource(self.manager, {'id': 42}, loaded=True)]
        result = self.manager._list("/human_resources", "human_resources")
        self.assertEqual(expected, result)

    def test_list_no_response_key(self):
        self.response.json.return_value = [{'id': 42}]
        expected = [HumanResource(self.manager, {'id': 42}, loaded=True)]
        result = self.manager._list("/human_resources")
        self.assertEqual(expected, result)

    def test_list_get(self):
        self.manager._list("/human_resources", "human_resources")
        self.manager.client.get.assert_called_with("/human_resources")

    def test_list_post(self):
        self.manager._list("/human_resources", "human_resources",
                           json={'id': 42})
        self.manager.client.post.assert_called_with("/human_resources",
                                                    json={'id': 42})

    def test_get(self):
        self.response.json.return_value = {'human_resources': {'id': 42}}
        expected = HumanResource(self.manager, {'id': 42}, loaded=True)
        result = self.manager._get("/human_resources/42", "human_resources")
        self.manager.client.get.assert_called_with("/human_resources/42")
        self.assertEqual(expected, result)

    def test_get_no_response_key(self):
        self.response.json.return_value = {'id': 42}
        expected = HumanResource(self.manager, {'id': 42}, loaded=True)
        result = self.manager._get("/human_resources/42")
        self.manager.client.get.assert_called_with("/human_resources/42")
        self.assertEqual(expected, result)

    def test_post(self):
        self.response.json.return_value = {'human_resources': {'id': 42}}
        expected = HumanResource(self.manager, {'id': 42}, loaded=True)
        result = self.manager._post("/human_resources",
                                    response_key="human_resources",
                                    json={'id': 42})
        self.manager.client.post.assert_called_with("/human_resources",
                                                    json={'id': 42})
        self.assertEqual(expected, result)

    def test_post_return_raw(self):
        self.response.json.return_value = {'human_resources': {'id': 42}}
        result = self.manager._post("/human_resources",
                                    response_key="human_resources",
                                    json={'id': 42}, return_raw=True)
        self.manager.client.post.assert_called_with("/human_resources",
                                                    json={'id': 42})
        self.assertEqual(result, {'id': 42})

    def test_post_no_response_key(self):
        self.response.json.return_value = {'id': 42}
        expected = HumanResource(self.manager, {'id': 42}, loaded=True)
        result = self.manager._post("/human_resources", json={'id': 42})
        self.manager.client.post.assert_called_with("/human_resources",
                                                    json={'id': 42})
        self.assertEqual(expected, result)


class CrudManagerTest(test.BaseTestCase):

    domain_id = "my-domain"
    crud_resource_id = "1"

    def setUp(self):
        super(CrudManagerTest, self).setUp()
        self.http_client = FakeHTTPClient()
        self.tc = TestClient(self.http_client)

    def test_create(self):
        crud_resource = self.tc.crud_resources.create()
        self.assertEqual(crud_resource.id, self.crud_resource_id)

    def test_list(self, domain=None, user=None):
        crud_resources = self.tc.crud_resources.list(
            base_url=None,
            domain_id=self.domain_id)
        self.assertEqual(len(crud_resources), 1)
        self.assertEqual(crud_resources[0].id, self.crud_resource_id)
        self.assertEqual(crud_resources[0].domain_id, self.domain_id)
        crud_resources = self.tc.crud_resources.list(
            base_url=None,
            domain_id="another-domain",
            another_attr=None)
        self.assertEqual(len(crud_resources), 0)

    def test_get(self):
        crud_resource = self.tc.crud_resources.get(self.crud_resource_id)
        self.assertEqual(crud_resource.id, self.crud_resource_id)
        fake_client.assert_has_keys(
            crud_resource._info,
            required=["id", "domain_id"],
            optional=["missing-attr"])

    def test_update(self):
        crud_resource = self.tc.crud_resources.update(
            crud_resource_id=self.crud_resource_id,
            domain_id=self.domain_id)
        self.assertEqual(crud_resource.id, self.crud_resource_id)
        self.assertEqual(crud_resource.domain_id, self.domain_id)

    def test_delete(self):
        resp = self.tc.crud_resources.delete(
            crud_resource_id=self.crud_resource_id)
        self.assertEqual(resp.status_code, 202)

    def test_head(self):
        ret = self.tc.crud_resources.head(
            crud_resource_id=self.crud_resource_id)
        self.assertTrue(ret)
