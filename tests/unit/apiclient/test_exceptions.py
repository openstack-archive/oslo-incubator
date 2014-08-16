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

from oslotest import base as test_base
import six

from openstack.common.apiclient import exceptions


class FakeResponse(object):
    json_data = {}

    def __init__(self, **kwargs):
        for key, value in six.iteritems(kwargs):
            setattr(self, key, value)

    def json(self):
        return self.json_data


class ExceptionsArgsTest(test_base.BaseTestCase):

    def assert_exception(self, ex_cls, method, url, status_code, json_data,
                         error_msg=None, error_details=None,
                         check_description=True):
        ex = exceptions.from_response(
            FakeResponse(status_code=status_code,
                         headers={"Content-Type": "application/json"},
                         json_data=json_data),
            method,
            url)

        self.assertTrue(isinstance(ex, ex_cls))
        if check_description:
            expected_msg = error_msg or json_data["error"]["message"]
            expected_details = error_details or json_data["error"]["details"]
            self.assertEqual(ex.message, expected_msg)
            self.assertEqual(ex.details, expected_details)
        self.assertEqual(ex.method, method)
        self.assertEqual(ex.url, url)
        self.assertEqual(ex.http_status, status_code)

    def test_from_response_known(self):
        method = "GET"
        url = "/fake"
        status_code = 400
        json_data = {"error": {"message": "fake message",
                               "details": "fake details"}}
        self.assert_exception(
            exceptions.BadRequest, method, url, status_code, json_data)

    def test_from_response_unknown(self):
        method = "POST"
        url = "/fake-unknown"
        status_code = 499
        json_data = {"error": {"message": "fake unknown message",
                               "details": "fake unknown details"}}
        self.assert_exception(
            exceptions.HTTPClientError, method, url, status_code, json_data)
        status_code = 600
        self.assert_exception(
            exceptions.HttpError, method, url, status_code, json_data)

    def test_from_response_non_openstack(self):
        method = "POST"
        url = "/fake-unknown"
        status_code = 400
        json_data = {"alien": 123}
        self.assert_exception(
            exceptions.BadRequest, method, url, status_code, json_data,
            check_description=False)

    def test_from_response_wsme(self):
        method = "GET"
        url = "/fake-wsme"
        status_code = 400
        json_data = {"error_message": {"debuginfo": None,
                                       "faultcode": "Client",
                                       "faultstring": "fake message"}}
        error_msg = ("%(faultcode)s: %(faultstring)s" %
                     json_data["error_message"])
        error_details = unicode(json_data)
        self.assert_exception(
            exceptions.BadRequest, method, url, status_code, json_data,
            error_msg, error_details)
