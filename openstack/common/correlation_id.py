# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack Foundation.
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

"""
Middleware that attaches a context to the WSGI request
"""

from openstack.common import wsgi
from openstack.common import uuidutils


class CorrelationIdMiddleware(wsgi.Middleware):

    def __init__(self, app, options):
        self.options = options
        super(CorrelationIdMiddleware, self).__init__(app)

    def process_request(self, req):
        correlation_id = \
            req.headers.get("X_CORRELATION_ID") or uuidutils.generate_uuid()
        req.headers['X_CORRELATION_ID'] = correlation_id


def factory(global_conf, **local_conf):
    """
    Factory method for paste.deploy
    """
    conf = global_conf.copy()
    conf.update(local_conf)

    def filter(app):
        return CorrelationIdMiddleware(app, conf)

    return filter
