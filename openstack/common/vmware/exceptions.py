# Copyright (c) 2014 VMware, Inc.
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

import six

from openstack.common.gettextutils import _
from openstack.common import log as logging

LOG = logging.getLogger(__name__)

ALREADY_EXISTS = 'AlreadyExists'
CANNOT_DELETE_FILE = 'CannotDeleteFile'
FILE_ALREADY_EXISTS = 'FileAlreadyExists'
FILE_FAULT = 'FileFault'
FILE_LOCKED = 'FileLocked'
FILE_NOT_FOUND = 'FileNotFound'
INVALID_PROPERTY = 'InvalidProperty'
NOT_AUTHENTICATED = 'NotAuthenticated'


class VimException(Exception):
    """The base exception class for all exceptions this library raises."""

    def __init__(self, message, cause=None):
        self.msg = message
        self.cause = cause

    def __str__(self):
        descr = self.msg
        if self.cause:
            descr += '\nCause: ' + str(self.cause)
        return descr


class VimSessionOverLoadException(VimException):
    """Thrown when there is an API call overload at the VMware server."""
    pass


class VimConnectionException(VimException):
    """Thrown when there is a connection problem."""
    pass


class VimAttributeException(VimException):
    """Thrown when a particular attribute cannot be found."""
    pass


class VimFaultException(VimException):
    """Exception thrown when there are faults during VIM API calls."""

    def __init__(self, fault_list, message, cause=None):
        super(VimFaultException, self).__init__(message, cause)
        self.fault_list = fault_list

    def __str__(self):
        descr = VimException.__str__(self)
        if self.fault_list:
            descr += '\nFaults: ' + str(self.fault_list)
        return descr


class ImageTransferException(VimException):
    """Thrown when there is an error during image transfer."""
    pass


class VMwareDriverException(Exception):
    """Base VMware Driver Exception

    To correctly use this class, inherit from it and define
    a 'msg_fmt' property. That msg_fmt will get printf'd
    with the keyword arguments provided to the constructor.

    """
    msg_fmt = _("An unknown exception occurred.")

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if not message:
            try:
                message = self.msg_fmt % kwargs

            except Exception:
                # kwargs doesn't match a variable in the message
                # log the issue and the kwargs
                LOG.exception(_('Exception in string format operation'))
                for name, value in six.iteritems(kwargs):
                    LOG.error("%s: %s" % (name, value))
                # at least get the core message out if something happened
                message = self.msg_fmt

        super(VMwareDriverException, self).__init__(message)


class AlreadyExistsException(VMwareDriverException):
    msg_fmt = _("Resource already exists.")


class CannotDeleteFileException(VMwareDriverException):
    msg_fmt = _("Cannot delete file.")


class FileAlreadyExistsException(VMwareDriverException):
    msg_fmt = _("File already exists.")


class FileFaultException(VMwareDriverException):
    msg_fmt = _("File fault.")


class FileLockedException(VMwareDriverException):
    msg_fmt = _("File locked.")


class FileNotFoundException(VMwareDriverException):
    msg_fmt = _("File not found.")


class InvalidPropertyException(VMwareDriverException):
    msg_fmt = _("Invalid property.")


class NotAuthenticatedException(VMwareDriverException):
    msg_fmt = _("Not Authenticated.")


# Populate the fault registry with the exceptions that have
# special treatment.
_fault_classes_registry = {
    ALREADY_EXISTS: AlreadyExistsException,
    CANNOT_DELETE_FILE: CannotDeleteFileException,
    FILE_ALREADY_EXISTS: FileAlreadyExistsException,
    FILE_FAULT: FileFaultException,
    FILE_LOCKED: FileLockedException,
    FILE_NOT_FOUND: FileNotFoundException,
    INVALID_PROPERTY: InvalidPropertyException,
    NOT_AUTHENTICATED: NotAuthenticatedException,
}


def get_fault_class(name):
    """Get a named subclass of NovaException."""
    name = str(name)
    fault_class = _fault_classes_registry.get(name)
    if not fault_class:
        LOG.debug(_('Fault %s not matched.'), name)
        fault_class = VMwareDriverException
    return fault_class
