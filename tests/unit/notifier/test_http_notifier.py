# Copyright 2012 NTT
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

"""Unit tests for HTTP Notifier."""

import httplib

import eventlet

from openstack.common import cfg
from openstack.common import log
from openstack.common.notifier import api as notifier_api
from tests import utils as test_utils


CONF = cfg.CONF


class HTTPNotifierTestCase(test_utils.BaseTestCase):
    """Test case for the HTTP notifier."""
    notification_driver = 'openstack.common.notifier.http_notifier'
    notification_event = "compute.instance.create.end"

    def setUp(self):
        super(HTTPNotifierTestCase, self).setUp()
        self.config(notification_driver=[self.notification_driver, ])
        CONF.import_opt('url', self.notification_driver, group='http_notify')
        opts = {'group': 'http_notify',
                'url': 'http://localhost:9999/notify'}
        self.config(**opts)
        self._stub_out_LOG(self.stubs)
        self._stub_out_greenthread(self.stubs)
        #clear the last log.
        self.debug = None
        self.warn = None
        self.exc = None

    def tearDown(self):
        notifier_api._reset_drivers()
        super(HTTPNotifierTestCase, self).tearDown()

    def _stub_out_http_request(self, stubs, return_code, raise_exc=False):
        class FakeConnection:
            def __init__(self, loc):
                pass

            def getresponse(self):
                return FakeResponse(return_code, "dummy response")

            def request(self, *_args, **_kwargs):
                if raise_exc:
                    raise IOError

            def close(self):
                pass

        class FakeResponse:
            def __init__(self, status, response_str):
                self.status = status
                self.response_str = response_str

            def read(self):
                return self.response_str

        stubs.Set(httplib, 'HTTPConnection', FakeConnection)

    def _stub_out_LOG(self, stubs):
        def debug(msg):
            self.debug = msg

        def warning(msg):
            self.warn = msg

        def exception(msg):
            self.exc = msg

        stubs.Set(log.getLogger(self.notification_driver), 'debug', debug)
        stubs.Set(log.getLogger(self.notification_driver), 'warning', warning)
        stubs.Set(log.getLogger(self.notification_driver), 'exception',
                  exception)

    def _stub_out_greenthread(self, stubs):
        def spawn_n(func, arg1, arg2):
            func(arg1, arg2)

        stubs.Set(eventlet.greenthread, 'spawn_n', spawn_n)

    class _dummy_context():
        request_id = "req-dummyrequestid"

    def test_valid_event(self):
        self._stub_out_http_request(self.stubs, 200)
        notifier_api.notify(self._dummy_context, 'publisher_id',
                            self.notification_event, "INFO", dict(a=3))

        self.assertNotEqual(self.debug, None, "HTTP notification failure")
        self.assertTrue(self.debug.startswith("HTTP notification successful."))

    def test_invalid_event(self):
        self._stub_out_http_request(self.stubs, 200)
        CONF.import_opt('filter', self.notification_driver,
                        group='http_notify')
        opts = {'group': 'http_notify',
                'filter': 'compute.instance.create.start'}
        self.config(**opts)
        # specify an event not present in the callback list.
        notifier_api.notify(self._dummy_context, 'publisher_id',
                            self.notification_event, "INFO", dict(a=3))

        msg = "HTTP Notification sent for invalid event '%s'." % \
              self.notification_event
        self.assertEqual(self.debug, None, msg)
        self.assertEqual(self.warn, None, msg)
        self.assertEqual(self.exc, None, msg)

    def test_invoke_exception(self):
        self._stub_out_http_request(self.stubs, 200, raise_exc=True)
        notifier_api.notify(self._dummy_context, 'publisher_id',
                            self.notification_event, "INFO", dict(a=3))

        self.assertNotEqual(self.exc, None,
                            "Warning message not logged for notification "
                            "error")
        self.assertTrue(self.exc.startswith(
                        "Connection error contacting notification server."))

    def test_notification_failure(self):
        self._stub_out_http_request(self.stubs, 500)
        notifier_api.notify(self._dummy_context, 'publisher_id',
                            self.notification_event, "INFO", dict(a=3))

        self.assertNotEqual(self.warn, None,
                            "Warning message not logged for notification "
                            "error")
        self.assertTrue(self.warn.startswith("HTTP notification failed."))
