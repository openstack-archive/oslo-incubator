# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2013 eNovance
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
"""
Send notifications on request

"""
import os.path
import sys
import traceback as tb

import webob.dec

from openstack.common import context
from openstack.common.middleware import base
from openstack.common.notifier import api


class RequestNotifier(base.Middleware):
    """Send notification on request."""

    @staticmethod
    def environ_to_dict(environ):
        return dict([(k, str(v))
                     for k, v in environ.iteritems()
                     if not k.startswith('wsgi.')])

    def process_request(self, request):
        payload = {
            'request': self.environ_to_dict(request.environ),
        }

        api.notify(context.get_admin_context(),
                   api.publisher_id(os.path.basename(sys.argv[0])),
                   'http.request',
                   api.INFO,
                   payload)

    def process_response(self, request, response,
                         exception=None, traceback=None):
        payload = {
            'request': self.environ_to_dict(request.environ),
        }

        if response:
            payload['response'] = {
                'status': response.status,
                'headers': response.headers,
            }

        if exception:
            payload['exception'] = {
                'value': repr(exception),
                'traceback': tb.format_tb(traceback)
            }

        api.notify(context.get_admin_context(),
                   api.publisher_id(os.path.basename(sys.argv[0])),
                   'http.response',
                   api.INFO,
                   payload)

    @webob.dec.wsgify
    def __call__(self, req):
        self.process_request(req)
        try:
            response = req.get_response(self.application)
        except Exception:
            type, value, traceback = sys.exc_info()
            self.process_response(req, None, value, traceback)
            raise
        else:
            self.process_response(req, response)
        return response
