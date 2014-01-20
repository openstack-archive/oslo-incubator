# Copyright (c) 2014 VMware, Inc.
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
Unit tests for read and write handles for image transfer.
"""

import mock

from openstack.common import test
from openstack.common.vmware import exceptions
from openstack.common.vmware import rw_handles
from openstack.common.vmware import vim_util


class FileHandleTest(test.BaseTestCase):
    """Tests for FileHandle."""

    def test_close(self):
        file_handle = mock.Mock()
        vmw_http_file = rw_handles.FileHandle(file_handle)
        vmw_http_file.close()
        file_handle.close.assert_called_once_with()

    def test_del(self):
        file_handle = mock.Mock()
        vmw_http_file = rw_handles.FileHandle(file_handle)
        del(vmw_http_file)
        file_handle.close.assert_called_once_with()

    def test_find_vmdk_url(self):
        device_url_0 = mock.Mock()
        device_url_0.disk = False
        device_url_1 = mock.Mock()
        device_url_1.disk = True
        device_url_1.url = 'https://*/ds1/vm1.vmdk'
        lease_info = mock.Mock()
        lease_info.deviceUrl = [device_url_0, device_url_1]
        host = '10.1.2.3'
        exp_url = 'https://%s/ds1/vm1.vmdk' % host
        vmw_http_file = rw_handles.FileHandle(None)
        self.assertEqual(exp_url, vmw_http_file._find_vmdk_url(lease_info,
                                                               host))


class FileWriteHandleTest(test.BaseTestCase):
    """Tests for FileWriteHandle."""

    def setUp(self):
        super(FileWriteHandleTest, self).setUp()

        vim_cookie = mock.Mock()
        vim_cookie.name = 'name'
        vim_cookie.value = 'value'

        self._conn = mock.Mock()
        patcher = mock.patch('httplib.HTTPConnection')
        self.addCleanup(patcher.stop)
        HTTPConnectionMock = patcher.start()
        HTTPConnectionMock.return_value = self._conn

        self.vmw_http_write_file = rw_handles.FileWriteHandle(
            '10.1.2.3', 'dc-0', 'ds-0', [vim_cookie], '1.vmdk', 100, 'http')

    def test_write(self):
        self.vmw_http_write_file.write(None)
        self._conn.send.assert_called_once_with(None)

    def test_close(self):
        self.vmw_http_write_file.close()
        self._conn.getresponse.assert_called_once_with()
        self._conn.close.assert_called_once_with()


class VmdkWriteHandleTest(test.BaseTestCase):
    """Tests for VmdkWriteHandle."""

    def setUp(self):
        super(VmdkWriteHandleTest, self).setUp()
        self._conn = mock.Mock()
        patcher = mock.patch('httplib.HTTPConnection')
        self.addCleanup(patcher.stop)
        HTTPConnectionMock = patcher.start()
        HTTPConnectionMock.return_value = self._conn

    def _create_mock_session(self, disk=True, progress=-1):
        device_url = mock.Mock()
        device_url.disk = disk
        device_url.url = 'http://*/ds/disk1.vmdk'
        lease_info = mock.Mock()
        lease_info.deviceUrl = [device_url]
        session = mock.Mock()

        def session_invoke_api_side_effect(module, method, *args, **kwargs):
            if module == session.vim:
                if method == 'ImportVApp':
                    return mock.Mock()
                elif method == 'HttpNfcLeaseProgress':
                    self.assertEqual(progress, kwargs['percent'])
                    return
            return lease_info

        session.invoke_api.side_effect = session_invoke_api_side_effect
        vim_cookie = mock.Mock()
        vim_cookie.name = 'name'
        vim_cookie.value = 'value'
        session.vim.client.options.transport.cookiejar = [vim_cookie]
        return session

    def test_init_failure(self):
        session = self._create_mock_session(False)
        self.assertRaises(exceptions.VimException,
                          lambda: rw_handles.VmdkWriteHandle(session,
                                                             '10.1.2.3',
                                                             'rp-1',
                                                             'folder-1',
                                                             None,
                                                             100))

    def test_write(self):
        session = self._create_mock_session()
        handle = rw_handles.VmdkWriteHandle(session, '10.1.2.3',
                                            'rp-1', 'folder-1', None,
                                            100)
        data = [1] * 10
        handle.write(data)
        self.assertEqual(len(data), handle._bytes_written)
        self._conn.send.assert_called_once_with(data)

    def test_update_progress(self):
        vmdk_size = 100
        data_size = 10
        session = self._create_mock_session(True, 10)
        handle = rw_handles.VmdkWriteHandle(session, '10.1.2.3',
                                            'rp-1', 'folder-1', None,
                                            vmdk_size)
        handle.write([1] * data_size)
        handle.update_progress()

    def test_update_progress_with_error(self):
        session = self._create_mock_session(True, 10)
        handle = rw_handles.VmdkWriteHandle(session, '10.1.2.3',
                                            'rp-1', 'folder-1', None,
                                            100)
        session.invoke_api.side_effect = exceptions.VimException(None)
        self.assertRaises(exceptions.VimException, handle.update_progress)

    def test_close(self):
        session = self._create_mock_session()
        handle = rw_handles.VmdkWriteHandle(session, '10.1.2.3',
                                            'rp-1', 'folder-1', None,
                                            100)

        def session_invoke_api_side_effect(module, method, *args, **kwargs):
            if module == vim_util and method == 'get_object_property':
                return 'ready'
            self.assertEqual(session.vim, module)
            self.assertEqual('HttpNfcLeaseComplete', method)

        session.invoke_api = mock.Mock(
            side_effect=session_invoke_api_side_effect)
        handle.close()
        self.assertEqual(2, session.invoke_api.call_count)


class VmdkReadHandleTest(test.BaseTestCase):
    """Tests for VmdkReadHandle."""

    def setUp(self):
        super(VmdkReadHandleTest, self).setUp()

        req_patcher = mock.patch('urllib2.Request')
        self.addCleanup(req_patcher.stop)
        RequestMock = req_patcher.start()
        RequestMock.return_value = mock.Mock()

        urlopen_patcher = mock.patch('urllib2.urlopen')
        self.addCleanup(urlopen_patcher.stop)
        urlopen_mock = urlopen_patcher.start()
        self._conn = mock.Mock()
        urlopen_mock.return_value = self._conn

    def _create_mock_session(self, disk=True, progress=-1):
        device_url = mock.Mock()
        device_url.disk = disk
        device_url.url = 'http://*/ds/disk1.vmdk'
        lease_info = mock.Mock()
        lease_info.deviceUrl = [device_url]
        session = mock.Mock()

        def session_invoke_api_side_effect(module, method, *args, **kwargs):
            if module == session.vim:
                if method == 'ExportVm':
                    return mock.Mock()
                elif method == 'HttpNfcLeaseProgress':
                    self.assertEqual(progress, kwargs['percent'])
                    return
            return lease_info

        session.invoke_api.side_effect = session_invoke_api_side_effect
        vim_cookie = mock.Mock()
        vim_cookie.name = 'name'
        vim_cookie.value = 'value'
        session.vim.client.options.transport.cookiejar = [vim_cookie]
        return session

    def test_init_failure(self):
        session = self._create_mock_session(False)
        self.assertRaises(exceptions.VimException,
                          lambda: rw_handles.VmdkReadHandle(session,
                                                            '10.1.2.3',
                                                            'vm-1',
                                                            '[ds] disk1.vmdk',
                                                            100))

    def test_read(self):
        chunk_size = rw_handles.READ_CHUNKSIZE
        session = self._create_mock_session()
        self._conn.read.return_value = [1] * chunk_size
        handle = rw_handles.VmdkReadHandle(session, '10.1.2.3',
                                           'vm-1', '[ds] disk1.vmdk',
                                           chunk_size * 10)
        handle.read(chunk_size)
        self.assertEqual(chunk_size, handle._bytes_read)
        self._conn.read.assert_called_once_with(chunk_size)

    def test_update_progress(self):
        chunk_size = rw_handles.READ_CHUNKSIZE
        vmdk_size = chunk_size * 10
        session = self._create_mock_session(True, 10)
        self._conn.read.return_value = [1] * chunk_size
        handle = rw_handles.VmdkReadHandle(session, '10.1.2.3',
                                           'vm-1', '[ds] disk1.vmdk',
                                           vmdk_size)
        handle.read(chunk_size)
        handle.update_progress()

    def test_update_progress_with_error(self):
        session = self._create_mock_session(True, 10)
        handle = rw_handles.VmdkReadHandle(session, '10.1.2.3',
                                           'vm-1', '[ds] disk1.vmdk',
                                           100)
        session.invoke_api.side_effect = exceptions.VimException(None)
        self.assertRaises(exceptions.VimException, handle.update_progress)

    def test_close(self):
        session = self._create_mock_session()
        handle = rw_handles.VmdkReadHandle(session, '10.1.2.3',
                                           'vm-1', '[ds] disk1.vmdk',
                                           100)

        def session_invoke_api_side_effect(module, method, *args, **kwargs):
            if module == vim_util and method == 'get_object_property':
                return 'ready'
            self.assertEqual(session.vim, module)
            self.assertEqual('HttpNfcLeaseComplete', method)

        session.invoke_api = mock.Mock(
            side_effect=session_invoke_api_side_effect)
        handle.close()
        self.assertEqual(2, session.invoke_api.call_count)


class ImageReadHandleTest(test.BaseTestCase):
    """Tests for ImageReadHandle."""

    def test_read(self):
        max_items = 10
        item = [1] * 10

        class ImageReadIterator:

            def __init__(self):
                self.num_items = 0

            def __iter__(self):
                return self

            def next(self):
                if (self.num_items < max_items):
                    self.num_items += 1
                    return item
                raise StopIteration

        handle = rw_handles.ImageReadHandle(ImageReadIterator())
        for _ in range(0, max_items):
            self.assertEqual(item, handle.read(10))
        self.assertFalse(handle.read(10))
