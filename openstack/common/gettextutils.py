# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
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
gettext for openstack-common modules.

Usual usage in an openstack.common module:

    from openstack.common.gettextutils import _
"""

import gettext


t = gettext.translation('openstack-common', 'locale', fallback=True)


def _(msg):
    return t.ugettext(msg)


def install(domain):
    import __builtin__
    if '_' in __builtin__.__dict__:
        if not hasattr('_', '__self__'):
            return
        trans = _.__self__
        if not isinstance(trans, gettext.NullTranslations):
            return
        t = gettext.translation(domain, fallback=True)
        trans.add_fallback(t)
    else:
        gettext.install(domain, unicode=1)
