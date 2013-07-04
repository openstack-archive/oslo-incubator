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
Exceptions common to OpenStack projects
"""

import logging

from openstack.common.gettextutils import _  # noqa

_FATAL_EXCEPTION_FORMAT_ERRORS = False

LOG = logging.getLogger(__name__)


class Error(Exception):
    def __init__(self, message=None):
        super(Error, self).__init__(message)


class ApiError(Error):
    def __init__(self, message='Unknown', code='Unknown'):
        self.api_message = message
        self.code = code
        super(ApiError, self).__init__('%s: %s' % (code, message))


class NotFound(Error):
    pass


class UnknownScheme(Error):

    msg_fmt = "Unknown scheme '%s' found in URI"

    def __init__(self, scheme):
        msg = self.msg_fmt % scheme
        super(UnknownScheme, self).__init__(msg)


class BadStoreUri(Error):

    msg_fmt = "The Store URI %s was malformed. Reason: %s"

    def __init__(self, uri, reason):
        msg = self.msg_fmt % (uri, reason)
        super(BadStoreUri, self).__init__(msg)


class Duplicate(Error):
    pass


class NotAuthorized(Error):
    pass


class NotEmpty(Error):
    pass


class Invalid(Error):
    pass


class BadInputError(Exception):
    """Error resulting from a client sending bad input to a server"""
    pass


class MissingArgumentError(Error):
    pass


class DatabaseMigrationError(Error):
    pass


class ClientConnectionError(Exception):
    """Error resulting from a client connecting to a server"""
    pass


def wrap_exception(f):
    def _wrap(*args, **kw):
        try:
            return f(*args, **kw)
        except Exception as e:
            if not isinstance(e, Error):
                logging.exception(_('Uncaught exception'))
                raise Error(str(e))
            raise
    _wrap.func_name = f.func_name
    return _wrap


class OpenstackException(Exception):
    """Base Exception class.

    To correctly use this class, inherit from it and define
    a 'msg_fmt' property. That message will get printf'd
    with the keyword arguments provided to the constructor.
    """
    msg_fmt = "An unknown exception occurred"

    def __init__(self, **kwargs):
        try:
            self._error_string = self.msg_fmt % kwargs

        except Exception:
            if _FATAL_EXCEPTION_FORMAT_ERRORS:
                raise
            else:
                # at least get the core message out if something happened
                self._error_string = self.msg_fmt

    def __str__(self):
        return self._error_string


class MalformedRequestBody(OpenstackException):
    msg_fmt = "Malformed message body: %(reason)s"


class InvalidContentType(OpenstackException):
    message = "Invalid content type %(content_type)s"


class QuotaException(Exception):
    """Base exception for quota."""

    message = _("Quota exception occurred.")
    code = 500
    headers = {}
    safe = False

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if 'code' not in self.kwargs:
            try:
                self.kwargs['code'] = self.code
            except AttributeError:
                pass

        if not message:
            try:
                message = self.message % kwargs

            except Exception:
                # kwargs doesn't match a variable in the message
                # log the issue and the kwargs
                LOG.exception(_('Exception in string format operation'))
                for name, value in kwargs.iteritems():
                    LOG.error("%s: %s" % (name, value))
                else:
                    # at least get the core message out if something happened
                    message = self.message

        super(QuotaException, self).__init__(message)

    def format_message(self):
        if self.__class__.__name__.endswith('_Remote'):
            return self.args[0]
        else:
            return unicode(self)


class QuotaError(QuotaException):
    message = _("Quota exceeded") + ": code=%(code)s"
    code = 413
    headers = {'Retry-After': 0}
    safe = True


class InvalidQuotaValue(QuotaException):
    message = _("Change would make usage less than 0 for the following "
                "resources: %(unders)s")


class OverQuota(QuotaException):
    message = _("Quota exceeded for resources: %(overs)s")


class QuotaResourceUnknown(QuotaException):
    message = _("Unknown quota resources %(unknown)s.")


class QuotaNotFound(QuotaException):
    code = 404
    message = _("Quota could not be found")


class QuotaUsageNotFound(QuotaNotFound):
    message = _("Quota usage for project %(project_id)s could not be found.")


class ProjectQuotaNotFound(QuotaNotFound):
    message = _("Quota for project %(project_id)s could not be found.")


class QuotaClassNotFound(QuotaNotFound):
    message = _("Quota class %(class_name)s could not be found.")


class ReservationNotFound(QuotaNotFound):
    message = _("Quota reservation %(uuid)s could not be found.")


class InvalidReservationExpiration(QuotaException):
    code = 400
    message = _("Invalid reservation expiration %(expire)s.")
