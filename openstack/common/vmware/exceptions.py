# Copyright (c) 2013 VMware, Inc.
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

NOT_AUTHENTICATED_FAULT = "NotAuthenticated"


class VimException(Exception):
    """The base exception class for all exceptions this library raises."""

    def __init__(self, message, cause=None):
        super(VimException, self).__init__(message)
        self.cause = cause

    def __str__(self):
        string = self.message
        if self.cause:
            string += '\nCause: ' + str(self.cause)
        return string


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
        string = VimException.__str__(self)
        if self.fault_list:
            string += '\nFaults: ' + str(self.fault_list)
        return string


class ImageTransferException(VimException):
    """Thrown when there is an error during image transfer."""
    pass
