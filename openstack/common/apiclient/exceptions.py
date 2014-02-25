# Copyright 2010 Jacob Kaplan-Moss
# Copyright 2011 Nebula, Inc.
# Copyright 2013 Alessio Ababilov
# Copyright 2013 OpenStack Foundation
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
Exception definitions.
"""

import webob.exc


class ClientException(Exception):
    """The base exception class for all exceptions this library raises.
    """
    pass


class UnsupportedVersion(ClientException):
    """User is trying to use an unsupported version of the API."""
    pass


class MissingArgs(ClientException):
    """Supplied arguments are not sufficient for calling a function."""
    def __init__(self, missing):
        self.missing = missing
        msg = "Missing argument(s): %s" % ", ".join(missing)
        super(MissingArgs, self).__init__(msg)


class ValidationError(ClientException):
    """Error in validation on API client side."""
    pass


class CommandError(ClientException):
    """Error in CLI tool."""
    pass


class AuthorizationFailure(ClientException):
    """Cannot authorize API client."""
    pass


class ConnectionRefused(ClientException):
    """Cannot connect to API service."""
    pass


class AuthPluginOptionsMissing(AuthorizationFailure):
    """Auth plugin misses some options."""
    def __init__(self, opt_names):
        super(AuthPluginOptionsMissing, self).__init__(
            "Authentication failed. Missing options: %s" %
            ", ".join(opt_names))
        self.opt_names = opt_names


class AuthSystemNotFound(AuthorizationFailure):
    """User has specified a AuthSystem that is not installed."""
    def __init__(self, auth_system):
        super(AuthSystemNotFound, self).__init__(
            "AuthSystemNotFound: %s" % repr(auth_system))
        self.auth_system = auth_system


class NoUniqueMatch(ClientException):
    """Multiple entities found instead of one."""
    pass


class EndpointException(ClientException):
    """Something is rotten in Service Catalog."""
    pass


class EndpointNotFound(EndpointException):
    """Could not find requested endpoint in Service Catalog."""
    pass


class AmbiguousEndpoints(EndpointException):
    """Found more than one matching endpoint in Service Catalog."""
    def __init__(self, endpoints=None):
        super(AmbiguousEndpoints, self).__init__(
            "AmbiguousEndpoints: %s" % repr(endpoints))
        self.endpoints = endpoints


# base http errors
HttpError = webob.exc.HTTPError
HTTPRedirection = webob.exc.HTTPRedirection
HTTPClientError = webob.exc.HTTPClientError
HttpServerError = webob.exc.HTTPServerError

# 3xx Redirection
MultipleChoices = webob.exc.HTTPMultipleChoices

# 4xx Client Errors
BadRequest = webob.exc.HTTPBadRequest
Unauthorized = webob.exc.HTTPUnauthorized
PaymentRequired = webob.exc.HTTPPaymentRequired
Forbidden = webob.exc.HTTPForbidden
NotFound = webob.exc.HTTPNotFound
MethodNotAllowed = webob.exc.HTTPMethodNotAllowed
NotAcceptable = webob.exc.HTTPNotAcceptable
ProxyAuthenticationRequired = webob.exc.HTTPProxyAuthenticationRequired
RequestTimeout = webob.exc.HTTPRequestTimeout
Conflict = webob.exc.HTTPConflict
Gone = webob.exc.HTTPGone
LengthRequired = webob.exc.HTTPLengthRequired
PreconditionFailed = webob.exc.HTTPPreconditionFailed
RequestEntityTooLarge = webob.exc.HTTPRequestEntityTooLarge
RequestUriTooLong = webob.exc.HTTPRequestURITooLong
UnsupportedMediaType = webob.exc.HTTPUnsupportedMediaType
ExpectationFailed = webob.exc.HTTPExpectationFailed
UnprocessableEntity = webob.exc.HTTPUnprocessableEntity

# 5xx Server Errors
InternalServerError = webob.exc.HTTPInternalServerError
HttpNotImplemented = webob.exc.HTTPNotImplemented
BadGateway = webob.exc.HTTPBadGateway
ServiceUnavailable = webob.exc.HTTPServiceUnavailable
GatewayTimeout = webob.exc.HTTPGatewayTimeout
HttpVersionNotSupported = webob.exc.HTTPVersionNotSupported
