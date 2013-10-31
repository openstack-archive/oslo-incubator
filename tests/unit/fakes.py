# Copyright 2012 Intel Inc, OpenStack Foundation.
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
Fakes For filter and weight tests.
"""

import gettext

from openstack.common.scheduler import weights


class FakeWeigher1(weights.BaseHostWeigher):
    def __init__(self):
        pass


class FakeWeigher2(weights.BaseHostWeigher):
    def __init__(self):
        pass


class FakeClass(object):
    def __init__(self):
        pass


class FakeTranslations(gettext.GNUTranslations):
    """A test GNUTranslations class that takes a map of msg -> translations."""

    def __init__(self, translations):
        self.translations = translations

    def ugettext(self, msgid):
        return self.translations.get(msgid, msgid)

    @staticmethod
    def translator(locales_map):
        """Returns a mock gettext.translation function that uses
        individual TestTranslations to translate in the given locales.

        :param locales_map: A map from locale name to a translations mapg.
                            {
                             'es': {'Hi': 'Hola", 'Bye': 'Adios'},
                             'zh': {'Hi': 'Ni Hao', 'Bye': 'Zaijian'}
                            }
        """
        def _translation(domain, localedir=None,
                         languages=None, fallback=None):
            if languages:
                language = languages.pop()
                if language in locales_map:
                    return FakeTranslations(locales_map[language])
            return gettext.NullTranslations()
        return _translation
