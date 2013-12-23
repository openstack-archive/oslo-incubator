# Copyright 2013 OpenStack Foundation.
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

"""Exceptions for the LVM library."""

import sys

from openstack.common.gettextutils import _
from openstack.common import log as logging


LOG = logging.getLogger(__name__)


class LVMException(Exception):
    """Base Brick Exception

    To correctly use this class, inherit from it and define
    a 'msg_fmt' property. That msg_fmt will get printf'd
    with the keyword arguments provided to the constructor.
    """
    msg_fmt = _("An unknown exception occurred.")
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
                message = self.msg_fmt % kwargs

            except Exception:
                exc_info = sys.exc_info()
                # kwargs doesn't match a variable in the message
                # log the issue and the kwargs
                msg = (_("Exception in string format operation.  msg='%s'")
                       % self.msg_fmt)
                LOG.exception(msg)
                for name, value in kwargs.iteritems():
                    LOG.error("%s: %s" % (name, value))

                # at least get the core message out if something happened
                message = self.msg_fmt

        super(LVMException, self).__init__(message)


class VolumeGroupNotFound(LVMException):
    message = _('Unable to find Volume Group: %(vg_name)s')


class VolumeGroupCreationFailed(LVMException):
    message = _('Failed to create Volume Group: %(vg_name)s')
