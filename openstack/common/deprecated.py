# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012 IBM
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

import warnings

from openstack.common import cfg
from openstack.common import exception
from openstack.common import log as logging

LOG = logging.getLogger(__name__)

deprecate_opts = [
    cfg.BoolOpt('fatal_deprecations',
                default=False,
                help='make deprecations fatal')
]

CONF = cfg.CONF
CONF.register_opts(deprecate_opts)


def _showwarning(message, category, filename, lineno, file=None, line=None):
    """
    Redirect warnings into logging.
    """
    LOG.warn(str(message))


# Install our warnings handler
warnings.showwarning = _showwarning


def warn(msg=""):
    """
    Warn of a deprecated config option that an operator has specified.
    This should be added in the code where we've made a change in how
    we use some operator changeable parameter to indicate that it will
    go away in a future version of OpenStack.
    """
    warnings.warn(_("Deprecated Config: %s") % msg)
    if CONF.fatal_deprecations:
        raise exception.DeprecatedConfig(message=msg)
