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


def from_response(response, **kwargs):
    """Returns an instance of :class:`HTTPError` or subclass based on response.

    :param response: instance of `requests.Response` class
    """
    error_kwargs = {'detail': kwargs}
    kwargs["request_id"] = response.headers.get("x-compute-request-id")
    kwargs['code'] = response.status_code
    if "retry-after" in response.headers:
        kwargs["retry_after"] = response.headers["retry-after"]

    content_type = response.headers.get("Content-Type", "")
    if content_type.startswith("application/json"):
        try:
            body = response.json()
        except ValueError:
            pass
        else:
            if isinstance(body, dict):
                error = list(body.values())[0]
                error_kwargs["message"] = error.get("message")
                kwargs["details"] = error.get("details")
    elif content_type.startswith("text/"):
        kwargs["details"] = response.text

    cls = webob.exc.status_map.get(response.status_code)
    if cls:
        # NOTE(akurilin): Exceptions `HTTPClientError` and `HTTPServerError`
        # are base exceptions. They have the same code as their children:
        #   HTTPClientError.code == HTTPBadRequest.code == 400
        #   HTTPServerError.code == HTTPInternalServerError.code == 500
        # This check help us to be sure in correctness of returning exception
        # for 400 and 500 status code.
        if response.status_code == 400:
            cls = webob.exc.HTTPBadRequest
        elif response.status_code == 500:
            cls = webob.exc.HTTPInternalServerError
    else:
        if 500 <= response.status_code < 600:
            cls = webob.exc.HTTPServerError
        elif 400 <= response.status_code < 500:
            cls = webob.exc.HTTPClientError
        else:
            cls = webob.exc.HTTPError
    return cls(**error_kwargs)
