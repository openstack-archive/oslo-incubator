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


import mock
import requests

from openstack.common.apiclient import exceptions
from openstack.common.apiclient import client

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


class ClientTest(utils.BaseTestCase):

    def test_building_a_service_catalog(self):
        sc = client.HttpClient(auth_response=SERVICE_CATALOG)

        self.assertRaises(exceptions.AmbiguousEndpoints, sc.url_for,
                          endpoint_type='publicURL',
                          service_type='compute')
        self.assertEquals(sc.url_for(endpoint_type='publicURL',
                                     service_type='compute',
                                     filter_attrs={'tenantId': '1'}),
                          "https://compute1.host/v2/1")
        self.assertEquals(sc.url_for(endpoint_type='publicURL',
                                     service_type='compute',
                                     filter_attrs={'tenantId': '2'}),
                          "https://compute1.host/v1.1/2")

        self.assertRaises(exceptions.EndpointNotFound, sc.url_for,
                          endpoint_type='publicURL',
                          service_type='compute',
                          filter_attrs={'region': 'South'})

    def test_building_a_service_catalog_insensitive_case(self):
        sc = client.HttpClient(auth_response=SERVICE_CATALOG)
        # Matching south (and catalog has South).
        self.assertRaises(exceptions.AmbiguousEndpoints, sc.url_for,
                          endpoint_type='publicURL',
                          service_type='volume',
                          filter_attrs={'region': 'south'})

    def test_client_with_timeout(self):
        instance = client.HttpClient(username='user',
                                     password='password',
                                     tenant_id='project',
                                     timeout=2,
                                     auth_url="http://www.blah.com")
        self.assertEqual(instance.timeout, 2)
        mock_request = mock.Mock()
        mock_request.return_value = requests.Response()
        mock_request.return_value.status_code = 200
        mock_request.return_value.headers = {
            'x-server-management-url': 'blah.com',
            'x-auth-token': 'blah',
        }
        with mock.patch('requests.Session.request', mock_request):
            instance.authenticate()
            requests.Session.request.assert_called_with(
                mock.ANY,
                mock.ANY,
                timeout=2,
                headers=mock.ANY,
                verify=mock.ANY,
                data=mock.ANY,
                allow_redirects=mock.ANY)
