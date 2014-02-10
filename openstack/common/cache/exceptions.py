# -*- coding: utf-8 -*-

# Copyright 2013 Metacloud, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import six

from openstack.common.gettextutils import _
from openstack.common import log
from openstack.common import strutils


LOG = log.getLogger(__name__)


class Error(Exception):

    message_format = None

    def __init__(self, message=None, **kwargs):
        try:
            message = self._build_message(message, **kwargs)
        except KeyError:
            LOG.warning(_('missing exception kwargs (programmer error)'))
            message = self.message_format
        super(Error, self).__init__(message)

    def _build_message(self, message, **kwargs):
        """Builds and returns an exception message.

        :raises: KeyError given insufficient kwargs

        """
        if not message:
            try:
                message = self.message_format % kwargs
            except UnicodeDecodeError:
                try:
                    kwargs = dict([(k, strutils.safe_decode(v)) for k, v in
                                   six.iteritems(kwargs)])
                except UnicodeDecodeError:
                    # NOTE(jamielennox): This is the complete failure case
                    # at least by showing the template we have some idea
                    # of where the error is coming from
                    message = self.message_format
                else:
                    message = self.message_format % kwargs

        return message


class LockTimeout(Error):
    message_format = _('Lock Timeout occurred for key, %(target)s')


class ConfigurationValidationError(Error):
    message_format = _('Configuration Validation Error: %(msg)s')


class RegionNotConfigured(Error):
    message_format = _('Cache Region %(region_name)s is not configured.')


class RegionAlreadyConfigured(Error):
    message_format = _('Cache Region %(region_name)s is already configured.')
