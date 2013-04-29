# Copyright 2010 Jacob Kaplan-Moss
# Copyright 2011 Nebula, Inc.
# Copyright 2013 Grid Dynamics

"""
Exception definitions.
"""

import sys


class ClientException(Exception):
    """
    The base exception class for all exceptions this library raises.
    """
    pass


class ValidationError(ClientException):
    pass


class UnsupportedVersion(ClientException):
    """Indicates that the user is trying to use an unsupported
    version of the API"""
    pass


class CommandError(ClientException):
    pass


class AuthorizationFailure(ClientException):
    pass


class NoUniqueMatch(ClientException):
    pass


class AuthSystemNotFound(ClientException):
    """When the user specify a AuthSystem but not installed."""
    def __init__(self, auth_system):
        self.auth_system = auth_system

    def __str__(self):
        return "AuthSystemNotFound: %s" % repr(self.auth_system)


class NoTokenLookupException(ClientException):
    """This form of authentication does not support looking up
       endpoints from an existing token."""
    pass


class EndpointNotFound(ClientException):
    """Could not find Service or Region in Service Catalog."""
    pass


class AmbiguousEndpoints(ClientException):
    """Found more than one matching endpoint in Service Catalog."""
    def __init__(self, endpoints=None):
        self.endpoints = endpoints

    def __str__(self):
        return "AmbiguousEndpoints: %s" % repr(self.endpoints)


class HttpError(ClientException):
    """
    The base exception class for all HTTP exceptions.
    """
    def __init__(self, code, message=None, details=None, request_id=None,
                 url=None, method=None):
        self.code = code
        self.message = message or self.__class__.message
        self.details = details
        self.request_id = request_id
        self.url = url
        self.method = method

    def __str__(self):
        formatted_string = "%s (HTTP %s)" % (self.message, self.code)
        if self.request_id:
            formatted_string += " (Request-ID: %s)" % self.request_id

        return formatted_string


class HttpClientError(HttpError):
    """Exception for cases in which the client seems to have erred"""

    pass


class HttpServerError(HttpError):
    """Exception for cases in which the server is aware that it has
    erred or is incapable of performing the request"""

    pass


class BadRequest(HttpClientError):
    """
    HTTP 400 - Bad Request.
    The request cannot be fulfilled due to bad syntax.
    """
    http_status = 400
    message = "Bad Request"


class Unauthorized(HttpClientError):
    """
    HTTP 401 - Unauthorized.
    Similar to 403 Forbidden, but specifically for use when authentication
    is required and has failed or has not yet been provided.
    """
    http_status = 401
    message = "Unauthorized"


class PaymentRequired(HttpClientError):
    """
    HTTP 402 - Payment Required.
    Reserved for future use.
    """
    http_status = 402
    message = "Payment Required"


class Forbidden(HttpClientError):
    """
    HTTP 403 - Forbidden.
    The request was a valid request, but the server is refusing to respond
    to it.
    """
    http_status = 403
    message = "Forbidden"


class NotFound(HttpClientError):
    """
    HTTP 404 - Not Found.
    The requested resource could not be found but may be available again
    in the future.
    """
    http_status = 404
    message = "Not Found"


class MethodNotAllowed(HttpClientError):
    """
    HTTP 405 - Method Not Allowed.
    A request was made of a resource using a request method not supported
    by that resource.
    """
    http_status = 405
    message = "Method Not Allowed"


class NotAcceptable(HttpClientError):
    """
    HTTP 406 - Not Acceptable.
    The requested resource is only capable of generating content not
    acceptable according to the Accept headers sent in the request.
    """
    http_status = 406
    message = "Not Acceptable"


class ProxyAuthenticationRequired(HttpClientError):
    """
    HTTP 407 - Proxy Authentication Required.
    The client must first authenticate itself with the proxy.
    """
    http_status = 407
    message = "Proxy Authentication Required"


class RequestTimeout(HttpClientError):
    """
    HTTP 408 - Request Timeout.
    The server timed out waiting for the request.
    """
    http_status = 408
    message = "Request Timeout"


class Conflict(HttpClientError):
    """
    HTTP 409 - Conflict.
    Indicates that the request could not be processed because of conflict
    in the request, such as an edit conflict.
    """
    http_status = 409
    message = "Conflict"


class Gone(HttpClientError):
    """
    HTTP 410 - Gone.
    Indicates that the resource requested is no longer available and will
    not be available again.
    """
    http_status = 410
    message = "Gone"


class LengthRequired(HttpClientError):
    """
    HTTP 411 - Length Required.
    The request did not specify the length of its content, which is
    required by the requested resource.
    """
    http_status = 411
    message = "Length Required"


class PreconditionFailed(HttpClientError):
    """
    HTTP 412 - Precondition Failed.
    The server does not meet one of the preconditions that the requester
    put on the request.
    """
    http_status = 412
    message = "Precondition Failed"


class RequestEntityTooLarge(HttpClientError):
    """
    HTTP 413 - Request Entity Too Large.
    The request is larger than the server is willing or able to process.
    """
    http_status = 413
    message = "Request Entity Too Large"


class RequestUriTooLong(HttpClientError):
    """
    HTTP 414 - Request-URI Too Long.
    The URI provided was too long for the server to process.
    """
    http_status = 414
    message = "Request-URI Too Long"


class UnsupportedMediaType(HttpClientError):
    """
    HTTP 415 - Unsupported Media Type.
    The request entity has a media type which the server or resource does
    not support.
    """
    http_status = 415
    message = "Unsupported Media Type"


class RequestedRangeNotSatisfiable(HttpClientError):
    """
    HTTP 416 - Requested Range Not Satisfiable.
    The client has asked for a portion of the file, but the server cannot
    supply that portion.
    """
    http_status = 416
    message = "Requested Range Not Satisfiable"


class ExpectationFailed(HttpClientError):
    """
    HTTP 417 - Expectation Failed.
    The server cannot meet the requirements of the Expect request-header field.
    """
    http_status = 417
    message = "Expectation Failed"


class UnprocessableEntity(HttpClientError):
    """
    HTTP 422 - Unprocessable Entity.
    The request was well-formed but was unable to be followed due to semantic
    errors.
    """
    http_status = 422
    message = "Unprocessable Entity"


class InternalServerError(HttpServerError):
    """
    HTTP 500 - Internal Server Error.
    A generic error message, given when no more specific message is suitable.
    """
    http_status = 500
    message = "Internal Server Error"


# NotImplemented is a python keyword.
class HttpNotImplemented(HttpServerError):
    """
    HTTP 501 - Not Implemented.
    The server either does not recognize the request method, or it lacks
    the ability to fulfill the request.
    """
    http_status = 501
    message = "Not Implemented"


class BadGateway(HttpServerError):
    """
    HTTP 502 - Bad Gateway.
    The server was acting as a gateway or proxy and received an invalid
    response from the upstream server.
    """
    http_status = 502
    message = "Bad Gateway"


class ServiceUnavailable(HttpServerError):
    """
    HTTP 503 - Service Unavailable.
    The server is currently unavailable.
    """
    http_status = 503
    message = "Service Unavailable"


class GatewayTimeout(HttpServerError):
    """
    HTTP 504 - Gateway Timeout.
    The server was acting as a gateway or proxy and did not receive a timely
    response from the upstream server.
    """
    http_status = 504
    message = "Gateway Timeout"


class HttpVersionNotSupported(HttpServerError):
    """
    HTTP 505 - HttpVersion Not Supported.
    The server does not support the HTTP protocol version used in the request.
    """
    http_status = 505
    message = "HTTP Version Not Supported"


# In Python 2.4 Exception is old-style and thus doesn't have a __subclasses__()
# so we can do this:
#     _code_map = dict((c.http_status, c)
#                      for c in HttpError.__subclasses__())
_code_map = {}
for obj in sys.modules[__name__].__dict__.values():
    if isinstance(obj, type):
        try:
            http_status = obj.http_status
        except AttributeError:
            pass
        else:
            _code_map[http_status] = obj


def from_response(response, body, method, url):
    """
    Return an instance of an HttpError or subclass
    based on an requests response.

    Usage::

        resp, body = requests.request(...)
        if resp.status_code != 200:
            raise exception_from_response(resp, rest.text)
    """
    cls = _code_map.get(response.status_code, ClientException)
    if response.headers:
        request_id = response.headers.get('x-compute-request-id')
    else:
        request_id = None
    if isinstance(body, dict):
        message = "n/a"
        details = "n/a"
        if hasattr(body, 'keys'):
            error = body[body.keys()[0]]
            message = error.get('message', None)
            details = error.get('details', None)
        return cls(code=response.status_code, message=message, details=details,
                   request_id=request_id, url=url, method=method)
    else:
        return cls(code=response.status_code, details=body,
                   request_id=request_id, url=url, method=method)
