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

import inspect

import six
from webob import exc as http_exc


class ClientException(Exception):
    """The base exception class for all exceptions this library raises.
    """
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


class UnsupportedVersion(ClientException):
    """User is trying to use an unsupported version of the API."""
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


# _code_map contains all the classes that have `code` attribute.
_code_map = dict(
    (getattr(obj, 'code', None), obj)
    for obj in six.itervalues(vars(http_exc))
    if inspect.isclass(obj) and getattr(obj, 'code', False)
)


def from_response(response, **kwargs):
    """Returns an instance of :class:`HttpError` or subclass based on response.

    :param response: instance of `requests.Response` class
    :param method: HTTP method used for request
    :param url: URL used for request
    """
    error_kwargs = {'detail': kwargs}

    kwargs["request_id"] = response.headers.get("x-compute-request-id")
    if "retry-after" in response.headers:
        kwargs["retry_after"] = response.headers["retry-after"]

    content_type = response.headers.get("Content-Type", "")
    if content_type.startswith("application/json"):
        try:
            body = response.json()
        except ValueError:
            pass
        else:
            if hasattr(body, "keys"):
                error = body[body.keys()[0]]
                error_kwargs["message"] = error.get("message", None)
                kwargs["details"] = error.get("details", None)
    elif content_type.startswith("text/"):
        kwargs["details"] = response.text

    try:
        cls = _code_map[response.status_code]
    except KeyError:
        if 500 <= response.status_code < 600:
            cls = http_exc.HTTPServerError
        elif 400 <= response.status_code < 500:
            cls = http_exc.HTTPClientError
        else:
            cls = http_exc.HTTPError
        cls.code = response.status_code
    return cls(**error_kwargs)
