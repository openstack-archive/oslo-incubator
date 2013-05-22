# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack Foundation
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

from openstack.common.apiclient.auth import response
from openstack.common.apiclient import exceptions
from openstack.common import timeutils

from tests import utils


# Taken directly from keystone/content/common/samples/auth.json
# Do not edit this structure. Instead, grab the latest from there.

SERVICE_CATALOG = {
    "access": {
        "token": {
            "id": "ab48a9efdfedb23ty3494",
            "expires": "2010-11-01T03:32:15-05:00",
            "tenant": {
                "id": "345",
                "name": "My Project"
            }
        },
        "user": {
            "id": "123",
            "name": "jqsmith",
            "roles": [
                {
                    "id": "234",
                    "name": "compute:admin",
                },
                {
                    "id": "235",
                    "name": "object-store:admin",
                    "tenantId": "1",
                }
            ],
            "roles_links": [],
        },
        "serviceCatalog": [
            {
                "name": "Cloud Servers",
                "type": "compute",
                "endpoints": [
                    {
                        # Tenant 1, no region, v1.0
                        "tenantId": "1",
                        "publicURL": "https://compute1.host/v1/1",
                        "internalURL": "https://compute1.host/v1/1",
                        "versionId": "1.0",
                        "versionInfo": "https://compute1.host/v1.0/",
                        "versionList": "https://compute1.host/"
                    },
                    {
                        # Tenant 2, with region, v1.1
                        "tenantId": "2",
                        "publicURL": "https://compute1.host/v1.1/2",
                        "internalURL": "https://compute1.host/v1.1/2",
                        "region": "North",
                        "versionId": "1.1",
                        "versionInfo": "https://compute1.host/v1.1/",
                        "versionList": "https://compute1.host/"
                    },
                    {
                        # Tenant 1, with region, v2.0
                        "tenantId": "1",
                        "publicURL": "https://compute1.host/v2/1",
                        "internalURL": "https://compute1.host/v2/1",
                        "region": "North",
                        "versionId": "2",
                        "versionInfo": "https://compute1.host/v2/",
                        "versionList": "https://compute1.host/"
                    },
                ],
                "endpoints_links": [],
            },
            {
                "name": "Nova Volumes",
                "type": "volume",
                "endpoints": [
                    {
                        "tenantId": "1",
                        "publicURL": "https://volume1.host/v1/1",
                        "internalURL": "https://volume1.host/v1/1",
                        "region": "South",
                        "versionId": "1.0",
                        "versionInfo": "uri",
                        "versionList": "uri"
                    },
                    {
                        "tenantId": "2",
                        "publicURL": "https://volume1.host/v1.1/2",
                        "internalURL": "https://volume1.host/v1.1/2",
                        "region": "South",
                        "versionId": "1.1",
                        "versionInfo": "https://volume1.host/v1.1/",
                        "versionList": "https://volume1.host/"
                    },
                ],
                "endpoints_links": [
                    {
                        "rel": "next",
                        "href": "https://identity1.host/v2.0/endpoints"
                    },
                ],
            },
        ],
        "serviceCatalog_links": [
            {
                "rel": "next",
                "href": "https://identity.host/v2.0/endpoints?session=2hfh8Ar",
            },
        ],
    },
}

UNSCOPED_TOKEN = {
    u'access': {u'serviceCatalog': {},
                u'token': {u'expires': u'2012-10-03T16:58:01Z',
                           u'id': u'3e2813b7ba0b4006840c3825860b86ed'},
                u'user': {u'id': u'c4da488862bd435c9e6c0275a0d0e49a',
                          u'name': u'exampleuser',
                          u'roles': [],
                          u'roles_links': [],
                          u'username': u'exampleuser'}
                }
}

PROJECT_SCOPED_TOKEN = {
    u'access': {
        u'serviceCatalog': [{
            u'endpoints': [{
    u'adminURL': u'http://admin:8776/v1/225da22d3ce34b15877ea70b2a575f58',
    u'internalURL':
    u'http://internal:8776/v1/225da22d3ce34b15877ea70b2a575f58',
    u'publicURL':
    u'http://public.com:8776/v1/225da22d3ce34b15877ea70b2a575f58',
    u'region': u'RegionOne'
            }],
            u'endpoints_links': [],
            u'name': u'Volume Service',
            u'type': u'volume'},
            {u'endpoints': [{
    u'adminURL': u'http://admin:9292/v1',
    u'internalURL': u'http://internal:9292/v1',
    u'publicURL': u'http://public.com:9292/v1',
    u'region': u'RegionOne'}],
                u'endpoints_links': [],
                u'name': u'Image Service',
                u'type': u'image'},
            {u'endpoints': [{
u'adminURL': u'http://admin:8774/v2/225da22d3ce34b15877ea70b2a575f58',
u'internalURL': u'http://internal:8774/v2/225da22d3ce34b15877ea70b2a575f58',
u'publicURL': u'http://public.com:8774/v2/225da22d3ce34b15877ea70b2a575f58',
u'region': u'RegionOne'}],
                u'endpoints_links': [],
                u'name': u'Compute Service',
                u'type': u'compute'},
            {u'endpoints': [{
u'adminURL': u'http://admin:8773/services/Admin',
u'internalURL': u'http://internal:8773/services/Cloud',
u'publicURL': u'http://public.com:8773/services/Cloud',
u'region': u'RegionOne'}],
                u'endpoints_links': [],
                u'name': u'EC2 Service',
                u'type': u'ec2'},
            {u'endpoints': [{
u'adminURL': u'http://admin:35357/v2.0',
u'internalURL': u'http://internal:5000/v2.0',
u'publicURL': u'http://public.com:5000/v2.0',
u'region': u'RegionOne'}],
                u'endpoints_links': [],
                u'name': u'Identity Service',
                u'type': u'identity'}],
        u'token': {u'expires': u'2012-10-03T16:53:36Z',
                   u'id': u'04c7d5ffaeef485f9dc69c06db285bdb',
                   u'tenant': {u'description': u'',
                               u'enabled': True,
                               u'id': u'225da22d3ce34b15877ea70b2a575f58',
                               u'name': u'exampleproject'}},
        u'user': {u'id': u'c4da488862bd435c9e6c0275a0d0e49a',
                  u'name': u'exampleuser',
                  u'roles': [{u'id': u'edc12489faa74ee0aca0b8a0b4d74a74',
                              u'name': u'Member'}],
                  u'roles_links': [],
                  u'username': u'exampleuser'}
    }
}


class AuthResponseTest(utils.BaseTestCase):

    def test_building_unscoped(self):
        auth_resp = response.AuthResponse(UNSCOPED_TOKEN)

        self.assertTrue(auth_resp)
        self.assertIn('access', auth_resp)

        self.assertEquals(auth_resp.token,
                          '3e2813b7ba0b4006840c3825860b86ed')
        self.assertEquals(auth_resp.username, 'exampleuser')
        self.assertEquals(auth_resp.user_id,
                          'c4da488862bd435c9e6c0275a0d0e49a')

        self.assertEquals(auth_resp.tenant_name, None)
        self.assertEquals(auth_resp.tenant_id, None)

        self.assertFalse(auth_resp.scoped)

        self.assertEquals(auth_resp.expires, timeutils.parse_isotime(
                          UNSCOPED_TOKEN['access']['token']['expires']))

    def test_building_scoped(self):
        auth_resp = response.AuthResponse(PROJECT_SCOPED_TOKEN)

        self.assertTrue(auth_resp)
        self.assertIn('access', auth_resp)

        self.assertEquals(auth_resp.token,
                          '04c7d5ffaeef485f9dc69c06db285bdb')
        self.assertEquals(auth_resp.username, 'exampleuser')
        self.assertEquals(auth_resp.user_id,
                          'c4da488862bd435c9e6c0275a0d0e49a')

        self.assertEquals(auth_resp.tenant_name, 'exampleproject')
        self.assertEquals(auth_resp.tenant_id,
                          '225da22d3ce34b15877ea70b2a575f58')

        self.assertEquals(auth_resp.tenant_name, auth_resp.project_name)
        self.assertEquals(auth_resp.tenant_id, auth_resp.project_id)

        self.assertTrue(auth_resp.scoped)

    def test_building_empty(self):
        auth_resp = response.AuthResponse({})

        self.assertFalse(auth_resp)
        self.assertEquals(auth_resp.expires, None)
        self.assertEquals(auth_resp.token, None)
        self.assertEquals(auth_resp.username, None)
        self.assertEquals(auth_resp.user_id, None)
        self.assertEquals(auth_resp.tenant_name, None)
        self.assertEquals(auth_resp.project_name, None)
        self.assertFalse(auth_resp.scoped)
        self.assertEquals(auth_resp.tenant_id, None)
        self.assertEquals(auth_resp.project_id, None)
        self.assertRaises(exceptions.EndpointNotFound,
                          auth_resp.url_for,
                          endpoint_type="publicURL",
                          service_type="compute",
                          filter_attrs={"region": "South"})

    def test_url_for(self):
        auth_resp = response.AuthResponse(SERVICE_CATALOG)

        self.assertRaises(exceptions.AmbiguousEndpoints,
                          auth_resp.url_for,
                          endpoint_type="publicURL",
                          service_type="compute")
        self.assertEquals(auth_resp.url_for(endpoint_type="publicURL",
                                            service_type="compute",
                                            filter_attrs={"tenantId": "1"}),
                          "https://compute1.host/v2/1")
        self.assertEquals(auth_resp.url_for(endpoint_type="publicURL",
                                            service_type="compute",
                                            filter_attrs={"tenantId": "2"}),
                          "https://compute1.host/v1.1/2")

        self.assertRaises(exceptions.EndpointNotFound,
                          auth_resp.url_for,
                          endpoint_type="publicURL",
                          service_type="compute",
                          filter_attrs={"region": "South"})

    def test_url_for_case_insensitive(self):
        auth_resp = response.AuthResponse(SERVICE_CATALOG)
        # Matching south (and catalog has South).
        self.assertRaises(exceptions.AmbiguousEndpoints,
                          auth_resp.url_for,
                          endpoint_type="publicURL",
                          service_type="volume",
                          filter_attrs={"region": "south"})
