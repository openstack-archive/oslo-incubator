# Copyright (c) 2014 Cisco Systems
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

import os

import webob

from openstack.common.middleware import base


class HealthCheckMiddleware(base.Middleware):
    """A middleware which provides basic application health checking.

    Returns:
        '200 OK' on success
        '503 DISABLE BY FILE' when administratively disabled
    """
    def __init__(self, application, **conf):
        self.application = application
        self.disable_file = conf.get('disable_file',
                                     '/etc/keystone/disable.txt')

    def _check_manual_disable(self):
        """Check for the presence of the `healthcheck_disable_file` flag.
        Returns True if exists on local disk.
        """
        return os.path.exists(self.disable_file)

    def _get(self, request):
        body, status = ('OK', 200)
        if self._check_manual_disable():
            body, status = ('DISABLED BY FILE', 503)

        return webob.Response(request=request, body=body,
                              content_type='text/plain', status=status)

    def process_request(self, request):
        if request.path == '/healthcheck':
            return self._get(request)
