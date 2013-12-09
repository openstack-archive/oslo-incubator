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

import mock
import webob.dec
import webob.exc

from openstack.common.middleware import catch_errors
from openstack.common import test


class CatchErrorsTest(test.BaseTestCase):

    def _test_has_request_id(self, application, expected_code=None):
        app = catch_errors.CatchErrorsMiddleware(application)
        req = webob.Request.blank('/test')
        res = req.get_response(app)
        self.assertEqual(expected_code, res.status_int)

    def test_success_response(self):
        @webob.dec.wsgify
        def application(req):
            return 'Hello, World!!!'

        self._test_has_request_id(application, webob.exc.HTTPOk.code)

    def test_internal_server_error(self):
        @webob.dec.wsgify
        def application(req):
            raise Exception()

        with mock.patch.object(catch_errors.LOG, 'exception') as log_exc:
            self._test_has_request_id(application,
                                      webob.exc.HTTPInternalServerError.code)
            self.assertEqual(1, log_exc.call_count)
