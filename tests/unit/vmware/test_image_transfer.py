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
Unit tests for functions and classes for image transfer.
"""

import math

import mock

from openstack.common import test
from openstack.common.vmware import exceptions
from openstack.common.vmware import image_transfer


class BlockingQueueTest(test.BaseTestCase):
    """Tests for BlockingQueue."""

    def test_read(self):
        max_size = 10
        chunk_size = 10
        max_transfer_size = 30
        queue = image_transfer.BlockingQueue(max_size, max_transfer_size)

        def get_side_effect():
            return [1] * chunk_size

        queue.get = mock.Mock(side_effect=get_side_effect)
        while True:
            data_item = queue.read(chunk_size)
            if not data_item:
                break

        self.assertEqual(max_transfer_size, queue._transferred)
        exp_calls = [mock.call()] * int(math.ceil(float(max_transfer_size) /
                                                  chunk_size))
        self.assertEqual(exp_calls, queue.get.call_args_list)

    def test_write(self):
        queue = image_transfer.BlockingQueue(10, 30)
        queue.put = mock.Mock()
        write_count = 10
        for _ in range(0, write_count):
            queue.write([1])
        exp_calls = [mock.call([1])] * write_count
        self.assertEqual(exp_calls, queue.put.call_args_list)

    def test_tell(self):
        max_transfer_size = 30
        queue = image_transfer.BlockingQueue(10, 30)
        self.assertEqual(max_transfer_size, queue.tell())


class ImageWriterTest(test.BaseTestCase):
    """Tests for ImageWriter class."""

    def _create_image_writer(self):
        self.image_service = mock.Mock()
        self.context = mock.Mock()
        self.input_file = mock.Mock()
        self.image_id = mock.Mock()
        return image_transfer.ImageWriter(self.context, self.input_file,
                                          self.image_service, self.image_id)

    def test_start(self):
        writer = self._create_image_writer()
        status_list = ['queued', 'saving', 'active']

        def image_service_show_side_effect(context, image_id):
            status = status_list.pop(0)
            return {'status': status}

        self.image_service.show.side_effect = image_service_show_side_effect
        exp_calls = [mock.call(self.context, self.image_id)] * len(status_list)
        with mock.patch.object(image_transfer,
                               'IMAGE_SERVICE_POLL_INTERVAL', 0):
            writer.start()
        self.assertTrue(writer.wait())
        self.image_service.update.assert_called_once_with(self.context,
                                                          self.image_id, {},
                                                          data=self.input_file)
        self.assertEqual(exp_calls, self.image_service.show.call_args_list)

    def test_start_with_killed_status(self):
        writer = self._create_image_writer()

        def image_service_show_side_effect(_context, _image_id):
            return {'status': 'killed'}

        self.image_service.show.side_effect = image_service_show_side_effect
        writer.start()
        self.assertRaises(exceptions.ImageTransferException,
                          writer.wait)
        self.image_service.update.assert_called_once_with(self.context,
                                                          self.image_id, {},
                                                          data=self.input_file)
        self.image_service.show.assert_called_once_with(self.context,
                                                        self.image_id)

    def test_start_with_unknown_status(self):
        writer = self._create_image_writer()

        def image_service_show_side_effect(_context, _image_id):
            return {'status': 'unknown'}

        self.image_service.show.side_effect = image_service_show_side_effect
        writer.start()
        self.assertRaises(exceptions.ImageTransferException,
                          writer.wait)
        self.image_service.update.assert_called_once_with(self.context,
                                                          self.image_id, {},
                                                          data=self.input_file)
        self.image_service.show.assert_called_once_with(self.context,
                                                        self.image_id)

    def test_start_with_image_service_show_exception(self):
        writer = self._create_image_writer()
        self.image_service.show.side_effect = RuntimeError()
        writer.start()
        self.assertRaises(exceptions.ImageTransferException, writer.wait)
        self.image_service.update.assert_called_once_with(self.context,
                                                          self.image_id, {},
                                                          data=self.input_file)
        self.image_service.show.assert_called_once_with(self.context,
                                                        self.image_id)


class FileReadWriteTaskTest(test.BaseTestCase):
    """Tests for FileReadWriteTask class."""

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
        rw_task = image_transfer.FileReadWriteTask(input_file, output_file)
        rw_task.start()
        self.assertTrue(rw_task.wait())
        self.assertEqual(len(data_items), input_file.read.call_count)

        exp_calls = []
        for i in range(0, len(data_items)):
            exp_calls.append(mock.call(data_items[i]))
        self.assertEqual(exp_calls, output_file.write.call_args_list)

        self.assertEqual(len(data_items),
                         input_file.update_progress.call_count)
        self.assertEqual(len(data_items),
                         output_file.update_progress.call_count)

    def test_start_with_read_exception(self):
        input_file = mock.Mock()
        input_file.read.side_effect = RuntimeError()
        output_file = mock.Mock()
        rw_task = image_transfer.FileReadWriteTask(input_file, output_file)
        rw_task.start()
        self.assertRaises(exceptions.ImageTransferException, rw_task.wait)
        input_file.read.assert_called_once_with(None)
