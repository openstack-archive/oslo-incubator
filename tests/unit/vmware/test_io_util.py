# Copyright (c) 2013 VMware, Inc.
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
Unit tests for utility classes for image transfer.
"""

import math
import mock

from openstack.common import test
from openstack.common.vmware import exceptions
from openstack.common.vmware import io_util


class ThreadSafePipeTest(test.BaseTestCase):
    """Tests for ThreadSafePipe."""

    def test_read(self):
        max_size = 10
        chunk_size = 10
        max_transfer_size = 30
        pipe = io_util.ThreadSafePipe(max_size, max_transfer_size)

        def get_side_effect():
            return [1] * chunk_size

        pipe.get = mock.Mock(side_effect=get_side_effect)
        while True:
            data_item = pipe.read(chunk_size)
            if not data_item:
                break

        self.assertEqual(max_transfer_size, pipe.transferred)
        exp_calls = [mock.call()] * int(math.ceil(float(max_transfer_size) /
                                                  chunk_size))
        self.assertEqual(pipe.get.call_args_list, exp_calls)

    def test_write(self):
        pipe = io_util.ThreadSafePipe(10, 30)
        pipe.put = mock.Mock()
        write_count = 10
        for _ in range(0, write_count):
            pipe.write([1])
        exp_calls = [mock.call([1])] * write_count
        self.assertEqual(pipe.put.call_args_list, exp_calls)

    def test_tell(self):
        max_transfer_size = 30
        pipe = io_util.ThreadSafePipe(10, 30)
        self.assertEqual(max_transfer_size, pipe.tell())


class GlanceWriteThreadTest(test.BaseTestCase):
    """Tests for GlanceWriteThread class."""

    def _create_write_thred(self):
        self.image_service = mock.Mock()
        self.context = mock.Mock()
        self.input_file = mock.Mock()
        self.image_id = mock.Mock()
        return io_util.GlanceWriteThread(self.context,
                                         self.input_file,
                                         self.image_service,
                                         self.image_id)

    def test_start(self):
        write_thread = self._create_write_thred()
        status_list = ['queued', 'saving', 'active']

        def image_service_show_side_effect(context, image_id):
            status = status_list.pop(0)
            return {'status': status}

        self.image_service.show.side_effect = image_service_show_side_effect
        exp_calls = [mock.call(self.context, self.image_id)] * len(status_list)
        with mock.patch.object(io_util.GlanceWriteThread,
                               'GLANCE_POLL_INTERVAL', 0):
            write_thread.start()
        self.assertTrue(write_thread.wait())
        self.image_service.update.assert_called_once_with(self.context,
                                                          self.image_id, {},
                                                          data=self.input_file)
        self.assertEqual(exp_calls, self.image_service.show.call_args_list)

    def test_start_with_killed_status(self):
        write_thread = self._create_write_thred()

        def image_service_show_side_effect(_context, _image_id):
            return {'status': 'killed'}

        self.image_service.show.side_effect = image_service_show_side_effect
        write_thread.start()
        self.assertRaises(exceptions.ImageTransferException,
                          write_thread.wait)
        self.image_service.update.assert_called_once_with(self.context,
                                                          self.image_id, {},
                                                          data=self.input_file)
        self.image_service.show.assert_called_once_with(self.context,
                                                        self.image_id)

    def test_start_with_unknown_status(self):
        write_thread = self._create_write_thred()

        def image_service_show_side_effect(_context, _image_id):
            return {'status': 'unknown'}

        self.image_service.show.side_effect = image_service_show_side_effect
        write_thread.start()
        self.assertRaises(exceptions.ImageTransferException,
                          write_thread.wait)
        self.image_service.update.assert_called_once_with(self.context,
                                                          self.image_id, {},
                                                          data=self.input_file)
        self.image_service.show.assert_called_once_with(self.context,
                                                        self.image_id)

    def test_start_with_image_service_show_exception(self):
        write_thread = self._create_write_thred()
        self.image_service.show.side_effect = RuntimeError()
        write_thread.start()
        self.assertRaises(RuntimeError, write_thread.wait)
        self.image_service.update.assert_called_once_with(self.context,
                                                          self.image_id, {},
                                                          data=self.input_file)
        self.image_service.show.assert_called_once_with(self.context,
                                                        self.image_id)


class IOThreadTest(test.BaseTestCase):
    """Tests for IOThread class."""

    def test_start(self):
        data_items = [[1] * 10, [1] * 20, [1] * 5, []]

        def input_file_read_side_effect(arg):
            self.assertFalse(arg)
            data = data_items[input_file_read_side_effect.i]
            input_file_read_side_effect.i += 1
            return data

        input_file_read_side_effect.i = 0
        input_file = mock.Mock()
        input_file.read.side_effect = input_file_read_side_effect
        output_file = mock.Mock()
        thread = io_util.IOThread(input_file, output_file)
        thread.start()
        self.assertTrue(thread.wait())
        self.assertEqual(input_file.read.call_count, len(data_items))

        exp_calls = []
        for i in range(0, len(data_items)):
            exp_calls.append(mock.call(data_items[i]))
        self.assertEqual(output_file.write.call_args_list, exp_calls)

        self.assertEqual(input_file.update_progress.call_count,
                         len(data_items))
        self.assertEqual(output_file.update_progress.call_count,
                         len(data_items))

    def test_start_with_read_exception(self):
        input_file = mock.Mock()
        input_file.read.side_effect = RuntimeError()
        output_file = mock.Mock()
        thread = io_util.IOThread(input_file, output_file)
        thread.start()
        self.assertRaises(RuntimeError, thread.wait)
        input_file.read.assert_called_once_with(None)
