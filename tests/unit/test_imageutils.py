# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (C) 2012 Yahoo! Inc.
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

from openstack.common import imageutils
from tests import utils as utils_test


class ImageUtilsTestCase(utils_test.BaseTestCase):
    def test_qemu_img_info_blank(self):
        example_output = """image: None
file_format: None
virtual_size: None
disk_size: None
cluster_size: None
backing_file: None"""
        image_info = imageutils.QemuImgInfo()
        self.assertEqual(str(image_info), example_output)
        self.assertEqual(len(image_info.snapshots), 0)

    def test_qemu_info_canon(self):
        example_output = """image: disk.config
file format: raw
virtual size: 64M (67108864 bytes)
cluster_size: 65536
disk size: 96K
blah BLAH: bb
"""
        image_info = imageutils.QemuImgInfo(example_output)
        self.assertEqual('disk.config', image_info.image)
        self.assertEqual('raw', image_info.file_format)
        self.assertEqual(67108864, image_info.virtual_size)
        self.assertEqual(98304, image_info.disk_size)
        self.assertEqual(65536, image_info.cluster_size)

    def test_qemu_info_canon2(self):
        example_output = """image: disk.config
file format: QCOW2
virtual size: 67108844
cluster_size: 65536
disk size: 963434
backing file: /var/lib/nova/a328c7998805951a_2
"""
        image_info = imageutils.QemuImgInfo(example_output)
        self.assertEqual('disk.config', image_info.image)
        self.assertEqual('qcow2', image_info.file_format)
        self.assertEqual(67108844, image_info.virtual_size)
        self.assertEqual(963434, image_info.disk_size)
        self.assertEqual(65536, image_info.cluster_size)
        self.assertEqual('/var/lib/nova/a328c7998805951a_2',
                         image_info.backing_file)

    def test_qemu_backing_file_actual(self):
        example_output = """image: disk.config
file format: raw
virtual size: 64M (67108864 bytes)
cluster_size: 65536
disk size: 96K
Snapshot list:
ID        TAG                 VM SIZE                DATE       VM CLOCK
1     d9a9784a500742a7bb95627bb3aace38      0 2012-08-20 10:52:46 00:00:00.000
backing file: /var/lib/nova/a328c7998805951a_2 (actual path: /b/3a988059e51a_2)
"""
        image_info = imageutils.QemuImgInfo(example_output)
        self.assertEqual('disk.config', image_info.image)
        self.assertEqual('raw', image_info.file_format)
        self.assertEqual(67108864, image_info.virtual_size)
        self.assertEqual(98304, image_info.disk_size)
        self.assertEqual(1, len(image_info.snapshots))
        self.assertEqual('/b/3a988059e51a_2',
                         image_info.backing_file)

    def test_qemu_info_convert(self):
        example_output = """image: disk.config
file format: raw
virtual size: 64M
disk size: 96K
Snapshot list:
ID        TAG                 VM SIZE                DATE       VM CLOCK
1        d9a9784a500742a7bb95627bb3aace38    0 2012-08-20 10:52:46 00:00:00.000
3        d9a9784a500742a7bb95627bb3aace38    0 2012-08-20 10:52:46 00:00:00.000
4        d9a9784a500742a7bb95627bb3aace38    0 2012-08-20 10:52:46 00:00:00.000
junk stuff: bbb
"""
        image_info = imageutils.QemuImgInfo(example_output)
        self.assertEqual('disk.config', image_info.image)
        self.assertEqual('raw', image_info.file_format)
        self.assertEqual(67108864, image_info.virtual_size)
        self.assertEqual(98304, image_info.disk_size)

    def test_qemu_info_snaps(self):
        example_output = """image: disk.config
file format: raw
virtual size: 64M (67108864 bytes)
disk size: 96K
Snapshot list:
ID        TAG                 VM SIZE                DATE       VM CLOCK
1        d9a9784a500742a7bb95627bb3aace38    0 2012-08-20 10:52:46 00:00:00.000
3        d9a9784a500742a7bb95627bb3aace38    0 2012-08-20 10:52:46 00:00:00.000
4        d9a9784a500742a7bb95627bb3aace38    0 2012-08-20 10:52:46 00:00:00.000
"""
        image_info = imageutils.QemuImgInfo(example_output)
        self.assertEqual('disk.config', image_info.image)
        self.assertEqual('raw', image_info.file_format)
        self.assertEqual(67108864, image_info.virtual_size)
        self.assertEqual(98304, image_info.disk_size)
        self.assertEqual(3, len(image_info.snapshots))
