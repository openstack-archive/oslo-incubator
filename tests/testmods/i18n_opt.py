# Copyright 2014 IBM Corp.
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

from oslo.config import cfg

from openstack.common import gettextutils

CONF = cfg.CONF

# Note that this is using the Message class directly instead of using
# gettextutils.enable_lazy() because this isolates the use of
# the Message class to this one instance instead of turning it on
# for all subsequent tests
opt = cfg.StrOpt('i18n', default="i18n",
                 help=gettextutils.Message('helpful message'))

CONF.register_opt(opt, group='i18n')
