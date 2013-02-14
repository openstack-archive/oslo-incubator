# Copyright (c) 2010-2012 OpenStack, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import webob.exc
import webob
from openstack.common import wsgi, strutils

"""
Cors Middleware
Middleware that adds Cross Origin Resource Sharing (short: CORS) headers. This
enables client-side javascript applications to manipulate OpenStack rest
services, without hosting the application on the same server as the OpenStack
services.

More information about CORS can be found at: http://www.w3.org/TR/cors/

Support among browsers is decent, with the notable exception of Internet
Explorer. IE7 doesn't support CORS, and will deny all cross-domain ajax. IE8
and IE9 do support CORS via the XDomainRequest, but limit the application
developer to GET and POST, without support for custom headers, and limited to
text/plain. This negates virtually all usecases in OpenStack context.

Proper support for CORS is present in:
- Internet Explorer 10
- Firefox 3.5
- Chrome (any)
- Safari 4.0
- Opera 12.0
- Safari Mobile 3.2
- Android 2.1
- BlackBerry 7.0
The best place for this middleware is early in the pipeline.
Configuration details:

[filter:cors]
paste.filter_factory = openstack.common.middleware.cors:filter_factory
## Allowed origins. Either a wildcard, or a space delimited list of domains.
## Note that these domains don't support wildcards of partial matches. This
## list is sent to the browser, and it is enforced by this middleware.
# allow_origin = *
## Methods to allow. A comma separated list of allowed methods. This is sent to
## the browser as-is; it is not enforced by this middleware.
# allow_methods = GET, POST, PUT, DELETE, OPTIONS
## A comma separated list of headers the client is allowed to customize. This
## is sent to the browser as-is; it is not enforced by this middleware
# allow_headers = Origin, Content-type, Accept, X-Auth-Token
## Whether the browser allows the app developper to send credentials.
# allow_credentials = false
## Whether this middleware responds to pre-flight OPTIONS requests. If you have
## implemented OPTIONS requests somewhere down the pipeline, you should switch
## this off. Even when switched off, the CORS headers are added to the
## response, so the pre-flight request will work as intended, but it may
## trigger unintended side-effects in your implementation.
# hijack_options = true
## The suggested cache time
# max_age = 3600
"""

DEFAULT_CONFIGURATION = {
    'allow_origin': '*',
    'allow_methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'allow_headers': 'Origin, Content-type, Accept, X-Auth-Token',
    'allow_credentials':  'false',
    'hijack_options': 'true',
    'max_age': '3600',
}


class CorsMiddleware(wsgi.Middleware):

    def __init__(self, app, conf):
        self.allowed_origins = set(conf['allow_origin'].split())
        self.hijack_options = strutils.bool_from_string(conf['hijack_options'])

        headers = {}
        headers['access-control-allow-origin'] = ' '.join(self.allowed_origins)
        headers['access-control-max-age'] = conf['max_age']
        headers['access-control-allow-methods'] = conf['allow_methods']
        headers['access-control-allow-headers'] = conf['allow_headers']
        headers['access-control-allow-credentials'] = conf['allow_credentials']
        self.cors_headers = headers
        super(CorsMiddleware, self).__init__(app)

    def process_request(self, req):
        """
        Enforce the allow_origin option, and optionally hijack OPTIONS reqs.
        """
        origin = req.headers.get('Origin')

        if origin not in self.allowed_origins and \
                '*' not in self.allowed_origins:
            return webob.exc.HTTPUnauthorized()

        if self.hijack_options and origin and req.method == 'OPTIONS':
            # Process the preflight response, by just sending an empty '200 OK'
            return self.process_response(webob.Response())

    def process_response(self, response):
        # add the necessary headers to the response.
        response.headers.update(self.cors_headers)
        return response


def filter_factory(global_conf, **local_conf):
    """
    Factory method for paste.deploy
    """

    conf = DEFAULT_CONFIGURATION.copy()
    conf.update(global_conf)
    conf.update(local_conf)

    def cors_filter(app):
        return CorsMiddleware(app, conf)

    return cors_filter
