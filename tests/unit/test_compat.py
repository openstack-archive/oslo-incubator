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

import tempfile

from openstack.common.py3kcompat import urlutils
from openstack.common import test


class CompatTestCase(test.BaseTestCase):
    def test_urlencode(self):
        fake = 'fake'
        result = urlutils.urlencode({'Fake': fake})
        self.assertEqual(result, 'Fake=fake')

    def test_urljoin(self):
        root_url = "http://yahoo.com/"
        url2 = "faq.html"
        result = urlutils.urljoin(root_url, url2)
        self.assertEqual(result, "http://yahoo.com/faq.html")

    def test_urlquote(self):
        url = "/~fake"
        result = urlutils.quote(url)
        self.assertEqual(result, '/%7Efake')

    def test_urlunquote(self):
        fake = "/%7Econnolly/"
        result = urlutils.unquote(fake)
        self.assertEqual(result, '/~connolly/')

    def test_urlparse(self):
        url = 'http://www.yahoo.com'
        result = urlutils.urlparse(url)
        self.assertEqual(result.scheme, 'http')

    def test_urlsplit(self):
        url = 'http://www.yahoo.com'
        result = urlutils.urlsplit(url)
        self.assertEqual(result.scheme, 'http')

    def test_urlunsplit(self):
        url = "http://www.yahoo.com"
        result = urlutils.urlunsplit(urlutils.urlsplit(url))
        self.assertEqual(result, 'http://www.yahoo.com')

    def test_urlopen(self):
        tmp = tempfile.NamedTemporaryFile()
        url = 'file://' + tmp.name
        result = urlutils.urlopen(url)
        self.assertEqual(result.url, url)
        tmp.close()

    def test_URLError(self):
        self.assertRaises(urlutils.URLError, urlutils.urlopen, 'wrong://url')

    def test_pathname2url(self):
        pathname = '~fake'
        result = urlutils.pathname2url(pathname)
        self.assertEqual(result, '%7Efake')
