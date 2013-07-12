# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 Canonical Ltd.
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
#

from openstack.common.py3kcompat import urlutils
from tests import utils


class CompatTestCase(utils.BaseTestCase):
    def test_urlencode(self):
        fake = 'fake'
        result = urlutils.urlencode({'Fake': fake})
        self.assertEquals(result, 'Fake=fake')

    def test_urlquote(self):
        url = "/~fake"
        result = urlutils.urlquote(url)
        self.assertEquals(result, '/%7Efake')

    def test_urlparse(self):
        url = 'http://www.yahoo.com'
        result = urlutils.urlparse(url)
        self.assertEquals(result.scheme, 'http')

    def test_urlsplit(self):
        url = 'http://www.yahoo.com'
        result = urlutils.urlsplit(url)
        self.assertEquals(result.scheme, 'http')

    def test_urlunsplit(self):
        url = "http://www.yahoo.com"
        result = urlutils.urlunsplit(urlutils.urlsplit(url))
        self.assertEquals(result, 'http://www.yahoo.com')
