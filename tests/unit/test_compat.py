# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (c) 2013 Canonical Ltd
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


from openstack.common.pycompat import text_type
from tests import utils


class CompatTextTests(utils.BaseTestCase):
    def _callCompat(self, *arg, **kwargs):
        from openstack.common.pycompat import text_
        return text_(*arg, **kwargs)

    def test_text_type(self):
        result = self._callCompat(text_type(b'123', 'ascii'))
        self.assertTrue(isinstance(result, text_type))
        self.assertEqual(result, text_type(b'123', 'ascii'))

    def test_binary_type(self):
        result = self._callCompat(b'123')
        self.assertTrue(isinstance(result, text_type))
        self.assertEqual(result, text_type(b'123', 'ascii'))


class CompatBytesTests(utils.BaseTestCase):
    def _callCompat(self, *arg, **kwargs):
        from openstack.common.pycompat import bytes_
        return bytes_(*arg, **kwargs)

    def bytes_binary_types(self):
        result = self._callCompat(b'123')
        self.assertTrue(isinstance(result, bytes))
        self.assertEqual(result, b'123')

    def bytes_text_types(self):
        val = text_type(b'123', 'ascii')
        result = self._callCompat(val)
        self.assertTrue(isinstance(result, bytes))
        self.assertEqual(result, b'123')
