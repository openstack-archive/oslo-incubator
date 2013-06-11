# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012 Red Hat, Inc.
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
Request Body limiting middleware.

"""

from oslo.config import cfg
import webob.dec
import webob.exc

from openstack.common.deprecated import wsgi
from openstack.common.gettextutils import _
from openstack.common.middleware import base


#default request size is 112k
max_req_body_size = cfg.IntOpt('max_request_body_size',
                               deprecated_name='osapi_max_request_body_size',
                               default=114688,
                               help='the maximum body size '
                                    'per each request(bytes)')

CONF = cfg.CONF
CONF.register_opt(max_req_body_size)


class LimitingReader(object):
    """Reader to limit the size of an incoming request."""
    def __init__(self, data, limit):
        """Initiates LimitingReader object.

        :param data: Underlying data object
        :param limit: maximum number of bytes the reader should allow
        """
        self.data = data
        self.limit = limit
        self.bytes_read = 0

    def __iter__(self):
        for chunk in self.data:
            self.bytes_read += len(chunk)
            if self.bytes_read > self.limit:
                msg = _("Request is too large.")
                raise webob.exc.HTTPRequestEntityTooLarge(explanation=msg)
            else:
                yield chunk

    def read(self, i=None):
        result = self.data.read(i)
        self.bytes_read += len(result)
        if self.bytes_read > self.limit:
            msg = _("Request is too large.")
            raise webob.exc.HTTPRequestEntityTooLarge(explanation=msg)
        return result


class RequestBodySizeLimiter(base.Middleware):
    """Limit the size of incoming requests."""

    def __init__(self, *args, **kwargs):
        super(RequestBodySizeLimiter, self).__init__(*args, **kwargs)

    @webob.dec.wsgify(RequestClass=wsgi.Request)
    def __call__(self, req):
        if req.content_length > CONF.max_request_body_size:
            msg = _("Request is too large.")
            raise webob.exc.HTTPRequestEntityTooLarge(explanation=msg)
        if req.content_length is None and req.is_body_readable:
            limiter = LimitingReader(req.body_file,
                                     CONF.max_request_body_size)
            req.body_file = limiter
        return self.application
