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


from oslotest import base as test_base
from testtools import matchers
import webob
import webob.dec

from openstack.common.middleware import request_id


class RequestIdTest(test_base.BaseTestCase):
    def test_generate_request_id(self):
        @webob.dec.wsgify
        def application(req):
            return req.environ[request_id.ENV_REQUEST_ID]

        app = request_id.RequestIdMiddleware(application)
        req = webob.Request.blank('/test')
        res = req.get_response(app)
        res_req_id = res.headers.get(request_id.HTTP_RESP_HEADER_REQUEST_ID)
        self.assertThat(res_req_id, matchers.StartsWith(b'req-'))
        # request-id in request environ is returned as response body
        self.assertEqual(res_req_id, res.body)
