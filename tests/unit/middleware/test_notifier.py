# Copyright 2013 eNovance
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

import mock
import webob

from openstack.common.middleware import notifier
from openstack.common.notifier import api
from tests import utils


class FakeApp(object):
    def __call__(self, env, start_response):
        body = 'Some response'
        start_response('200 OK', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(sum(map(len, body))))
        ])
        return [body]


class FakeFailingApp(object):
    def __call__(self, env, start_response):
        raise Exception("It happens!")


class NotifierMiddlewareTest(utils.BaseTestCase):

    def test_notification(self):
        middleware = notifier.RequestNotifier(FakeApp())
        req = webob.Request.blank('/foo/bar',
                                  environ={'REQUEST_METHOD': 'GET',
                                           'HTTP_X_AUTH_TOKEN': uuid.uuid4()})
        with mock.patch('openstack.common.notifier.api.notify') as notify:
            middleware(req)
            # Check first notification with only 'request'
            call_args = notify.call_args_list[0][0]
            self.assertEqual(call_args[2], 'http.request')
            self.assertEqual(call_args[3], api.INFO)
            self.assertEqual(set(call_args[4].keys()),
                             set(['request']))

            request = call_args[4]['request']
            self.assertEqual(request['PATH_INFO'], '/foo/bar')
            self.assertEqual(request['REQUEST_METHOD'], 'GET')
            self.assertIn('HTTP_X_SERVICE_NAME', request)
            self.assertNotIn('HTTP_X_AUTH_TOKEN', request)
            self.assertFalse(any(map(lambda s: s.startswith('wsgi.'),
                                     request.keys())),
                             "WSGI fields are filtered out")

            # Check second notification with request + response
            call_args = notify.call_args_list[1][0]
            self.assertEqual(call_args[2], 'http.response')
            self.assertEqual(call_args[3], api.INFO)
            self.assertEqual(set(call_args[4].keys()),
                             set(['request', 'response']))

            request = call_args[4]['request']
            self.assertEqual(request['PATH_INFO'], '/foo/bar')
            self.assertEqual(request['REQUEST_METHOD'], 'GET')
            self.assertIn('HTTP_X_SERVICE_NAME', request)
            self.assertNotIn('HTTP_X_AUTH_TOKEN', request)
            self.assertFalse(any(map(lambda s: s.startswith('wsgi.'),
                                     request.keys())),
                             "WSGI fields are filtered out")

            response = call_args[4]['response']
            self.assertEqual(response['status'], '200 OK')
            self.assertEqual(response['headers']['content-length'], '13')

    def test_notification_response_failure(self):
        middleware = notifier.RequestNotifier(FakeFailingApp())
        req = webob.Request.blank('/foo/bar',
                                  environ={'REQUEST_METHOD': 'GET',
                                           'HTTP_X_AUTH_TOKEN': uuid.uuid4()})
        with mock.patch('openstack.common.notifier.api.notify') as notify:
            try:
                middleware(req)
                self.fail("Application exception has not been re-raised")
            except Exception:
                pass
            # Check first notification with only 'request'
            call_args = notify.call_args_list[0][0]
            self.assertEqual(call_args[2], 'http.request')
            self.assertEqual(call_args[3], api.INFO)
            self.assertEqual(set(call_args[4].keys()),
                             set(['request']))

            request = call_args[4]['request']
            self.assertEqual(request['PATH_INFO'], '/foo/bar')
            self.assertEqual(request['REQUEST_METHOD'], 'GET')
            self.assertIn('HTTP_X_SERVICE_NAME', request)
            self.assertNotIn('HTTP_X_AUTH_TOKEN', request)
            self.assertFalse(any(map(lambda s: s.startswith('wsgi.'),
                                     request.keys())),
                             "WSGI fields are filtered out")

            # Check second notification with 'request' and 'exception'
            call_args = notify.call_args_list[1][0]
            self.assertEqual(call_args[2], 'http.response')
            self.assertEqual(call_args[3], api.INFO)
            self.assertEqual(set(call_args[4].keys()),
                             set(['request', 'exception']))

            request = call_args[4]['request']
            self.assertEqual(request['PATH_INFO'], '/foo/bar')
            self.assertEqual(request['REQUEST_METHOD'], 'GET')
            self.assertIn('HTTP_X_SERVICE_NAME', request)
            self.assertNotIn('HTTP_X_AUTH_TOKEN', request)
            self.assertFalse(any(map(lambda s: s.startswith('wsgi.'),
                                     request.keys())),
                             "WSGI fields are filtered out")

            exception = call_args[4]['exception']
            self.assertIn('notifier.py', exception['traceback'][0])
            self.assertIn('It happens!', exception['traceback'][-1])
            self.assertEqual(exception['value'], "Exception('It happens!',)")

    def test_process_request_fail(self):
        def notify_error(context, publisher_id, event_type,
                         priority, payload):
            raise Exception('error')
        self.stubs.Set(api, 'notify', notify_error)
        middleware = notifier.RequestNotifier(FakeApp())
        req = webob.Request.blank('/foo/bar',
                                  environ={'REQUEST_METHOD': 'GET'})
        middleware.process_request(req)

    def test_process_response_fail(self):
        def notify_error(context, publisher_id, event_type,
                         priority, payload):
            raise Exception('error')
        self.stubs.Set(api, 'notify', notify_error)
        middleware = notifier.RequestNotifier(FakeApp())
        req = webob.Request.blank('/foo/bar',
                                  environ={'REQUEST_METHOD': 'GET'})
        middleware.process_response(req, webob.response.Response())

    def test_ignore_req_opt(self):
        middleware = notifier.RequestNotifier(FakeApp(),
                                              ignore_req_list='get, PUT')
        req = webob.Request.blank('/skip/foo',
                                  environ={'REQUEST_METHOD': 'GET'})
        req1 = webob.Request.blank('/skip/foo',
                                   environ={'REQUEST_METHOD': 'PUT'})
        req2 = webob.Request.blank('/accept/foo',
                                   environ={'REQUEST_METHOD': 'POST'})
        with mock.patch('openstack.common.notifier.api.notify') as notify:
            # Check GET request does not send notification
            middleware(req)
            middleware(req1)
            self.assertEqual(len(notify.call_args_list), 0)

            # Check non-GET request does send notification
            middleware(req2)
            self.assertEqual(len(notify.call_args_list), 2)
            call_args = notify.call_args_list[0][0]
            self.assertEqual(call_args[2], 'http.request')
            self.assertEqual(call_args[3], api.INFO)
            self.assertEqual(set(call_args[4].keys()),
                             set(['request']))

            request = call_args[4]['request']
            self.assertEqual(request['PATH_INFO'], '/accept/foo')
            self.assertEqual(request['REQUEST_METHOD'], 'POST')

            call_args = notify.call_args_list[1][0]
            self.assertEqual(call_args[2], 'http.response')
            self.assertEqual(call_args[3], api.INFO)
            self.assertEqual(set(call_args[4].keys()),
                             set(['request', 'response']))
