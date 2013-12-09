# Copyright (c) 2013 NEC Corporation
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


from testtools import matchers
import webob.dec
import webob.exc

from openstack.common.middleware import catch_errors
from openstack.common import test


class CatchErrorsTest(test.BaseTestCase):

    def _test_has_request_id(self, application, expected_code=None,
                             expect_errors=False, request_id=None):
        app = catch_errors.CatchErrorsMiddleware(application)
        # app = webtest.TestApp(app)
        # res = app.get('/test', expect_errors=expect_errors)
        req = webob.Request.blank('/test')
        if request_id:
            req.environ[catch_errors.ENV_REQUEST_ID] = request_id
        res = req.get_response(app)
        self.assertEqual(expected_code, res.status_int)
        res_req_id = res.headers.get(catch_errors.HTTP_RESP_HEADER_REQUEST_ID)
        self.assertIsNotNone(res_req_id)
        if request_id:
            self.assertEqual(res_req_id, request_id)
        else:
            self.assertThat(res_req_id, matchers.StartsWith('req-'))

    def test_success_response_has_request_id(self):
        @webob.dec.wsgify
        def application(req):
            return 'Hello, World!!!'

        self._test_has_request_id(application, webob.exc.HTTPOk.code)

    def test_error_response_has_request_id(self):
        @webob.dec.wsgify
        def application(req):
            raise webob.exc.HTTPNotFound()

        self._test_has_request_id(application, webob.exc.HTTPNotFound.code,
                                  expect_errors=True)

    def test_internal_server_error_response_has_request_id(self):
        @webob.dec.wsgify
        def application(req):
            raise Exception()

        self._test_has_request_id(application,
                                  webob.exc.HTTPInternalServerError.code,
                                  expect_errors=True)

    def test_request_id_already_exists(self):
        @webob.dec.wsgify
        def application(req):
            return 'Hello, World!!!'

        self._test_has_request_id(application, webob.exc.HTTPOk.code,
                                  request_id='preset-id')
