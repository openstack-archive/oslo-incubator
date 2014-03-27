# Copyright 2012 OpenStack Foundation.
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

from openstack.common import network_utils
from openstack.common import test


class NetworkUtilsTest(test.BaseTestCase):

    def test_parse_host_port(self):
        self.assertEqual(('server01', 80),
                         network_utils.parse_host_port('server01:80'))
        self.assertEqual(('server01', None),
                         network_utils.parse_host_port('server01'))
        self.assertEqual(('server01', 1234),
                         network_utils.parse_host_port('server01',
                         default_port=1234))
        self.assertEqual(('::1', 80),
                         network_utils.parse_host_port('[::1]:80'))
        self.assertEqual(('::1', None),
                         network_utils.parse_host_port('[::1]'))
        self.assertEqual(('::1', 1234),
                         network_utils.parse_host_port('[::1]',
                         default_port=1234))
        self.assertEqual(('2001:db8:85a3::8a2e:370:7334', 1234),
                         network_utils.parse_host_port(
                             '2001:db8:85a3::8a2e:370:7334',
                             default_port=1234))

    def test_urlsplit(self):
        result = network_utils.urlsplit('rpc://myhost?someparam#somefragment')
        self.assertEqual(result.scheme, 'rpc')
        self.assertEqual(result.netloc, 'myhost')
        self.assertEqual(result.path, '')
        self.assertEqual(result.query, 'someparam')
        self.assertEqual(result.fragment, 'somefragment')

        result = network_utils.urlsplit(
            'rpc://myhost/mypath?someparam#somefragment',
            allow_fragments=False)
        self.assertEqual(result.scheme, 'rpc')
        self.assertEqual(result.netloc, 'myhost')
        self.assertEqual(result.path, '/mypath')
        self.assertEqual(result.query, 'someparam#somefragment')
        self.assertEqual(result.fragment, '')

        result = network_utils.urlsplit(
            'rpc://user:pass@myhost/mypath?someparam#somefragment',
            allow_fragments=False)
        self.assertEqual(result.scheme, 'rpc')
        self.assertEqual(result.netloc, 'user:pass@myhost')
        self.assertEqual(result.path, '/mypath')
        self.assertEqual(result.query, 'someparam#somefragment')
        self.assertEqual(result.fragment, '')

    def test_urlsplit_ipv6(self):
        ipv6_url = 'http://[::1]:443/v2.0/'
        result = network_utils.urlsplit(ipv6_url)
        self.assertEqual(result.scheme, 'http')
        self.assertEqual(result.netloc, '[::1]:443')
        self.assertEqual(result.path, '/v2.0/')
        self.assertEqual(result.hostname, '::1')
        self.assertEqual(result.port, 443)

        ipv6_url = 'http://user:pass@[::1]/v2.0/'
        result = network_utils.urlsplit(ipv6_url)
        self.assertEqual(result.scheme, 'http')
        self.assertEqual(result.netloc, 'user:pass@[::1]')
        self.assertEqual(result.path, '/v2.0/')
        self.assertEqual(result.hostname, '::1')
        self.assertEqual(result.port, None)

        ipv6_url = 'https://[2001:db8:85a3::8a2e:370:7334]:1234/v2.0/xy?ab#12'
        result = network_utils.urlsplit(ipv6_url)
        self.assertEqual(result.scheme, 'https')
        self.assertEqual(result.netloc, '[2001:db8:85a3::8a2e:370:7334]:1234')
        self.assertEqual(result.path, '/v2.0/xy')
        self.assertEqual(result.hostname, '2001:db8:85a3::8a2e:370:7334')
        self.assertEqual(result.port, 1234)
