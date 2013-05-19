# Copyright 2012 OpenStack LLC.
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

from tests import utils

from openstack.common.apiclient import exceptions


class FakeResponse(object):
    json_data = {}

    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    def json(self):
        return self.json_data


class ExceptionsArgsTest(utils.BaseTestCase):

    def test_from_response(self):
        method = "GET"
        url = "/fake"
        status_code = 400
        headers = {"Content-Type": "application/json"}
        json_data = {"error": {"message": "fake message",
                               "details": "fake details"}}
        out = exceptions.from_response(
            FakeResponse(status_code=status_code,
                         headers=headers,
                         json_data=json_data),
            method,
            url)
        self.assertTrue(isinstance(out, exceptions.BadRequest))
        self.assertEqual(out.message, json_data["error"]["message"])
        self.assertEqual(out.details, json_data["error"]["details"])
        self.assertEqual(out.method, method)
        self.assertEqual(out.url, url)
        self.assertEqual(out.code, status_code)
