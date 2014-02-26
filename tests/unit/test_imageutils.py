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

import testscenarios

from openstack.common import imageutils
from openstack.common import test

load_tests = testscenarios.load_tests_apply_scenarios


class ImageUtilsTestCase(test.BaseTestCase):

    """
    _template = '\n'.join([
    """

    _image_name = [
        ('disk_config', dict(image_name='disk.config')),
    ]

    _file_format = [
        ('raw', dict(file_format='raw')),
        ('qcow2', dict(file_format='qcow2')),
    ]

    _virtual_size = [
        ('64M', dict(virtual_size='64M',
                     exp_virtual_size=67108864)),
        ('64M_with_byte_hint', dict(virtual_size='64M (67108864 bytes)',
                                    exp_virtual_size=67108864)),
        ('64M_byte', dict(virtual_size='67108844',
                          exp_virtual_size=67108844)),
        ('2K', dict(virtual_size='2K',
                    exp_virtual_size=2048)),
        ('2K_with_byte_hint', dict(virtual_size='2K (2048 bytes)',
                                   exp_virtual_size=2048)),
    ]

    _disk_size = [
        ('96K', dict(disk_size='96K',
                     exp_disk_size=98304)),
        ('96K_byte', dict(disk_size='963434',
                          exp_disk_size=963434)),
    ]

    _garbage_before_snapshot = [
        ('no_garbage', dict(garbage_before_snapshot=None)),
        ('garbage_before_snapshot_list', dict(garbage_before_snapshot=False)),
        ('garbage_after_snapshot_list', dict(garbage_before_snapshot=True)),
    ]

    _snapshot_count = [
        ('no_snapshots', dict(snapshot_count=None)),
        ('one_snapshots', dict(snapshot_count=1)),
        ('three_snapshots', dict(snapshot_count=3)),
    ]

    _qcow2_cluster_size = [
        ('65536', dict(cluster_size='65536', exp_cluster_size=65536)),
    ]

    _qcow2_encrypted = [
        ('no_encryption', dict(encrypted=None)),
        ('encrypted', dict(encrypted='yes')),
    ]

    _qcow2_backing_file = [
        ('no_backing_file', dict(backing_file=None)),
        ('backing_file_path',
         dict(backing_file='/var/lib/nova/a328c7998805951a_2',
              exp_backing_file='/var/lib/nova/a328c7998805951a_2')),
        ('backing_file_path_with_actual_path',
         dict(backing_file='/var/lib/nova/a328c7998805951a_2 '
                           '(actual path: /b/3a988059e51a_2)',
              exp_backing_file='/b/3a988059e51a_2')),
    ]

    @classmethod
    def generate_scenarios(cls):
        cls.scenarios = testscenarios.multiply_scenarios(
            cls._image_name,
            cls._file_format,
            cls._virtual_size,
            cls._disk_size,
            cls._snapshot_count,
            cls._garbage_before_snapshot,
            cls._qcow2_cluster_size,
            cls._qcow2_encrypted,
            cls._qcow2_backing_file)

    def test_qemu_img_info(self):
        img_info = ('image: %s' % self.image_name,
                    'file_format: %s' % self.file_format,
                    'virtual_size: %s' % self.virtual_size,
                    'disk_size: %s' % self.disk_size)
        if self.file_format == 'qcow2':
            img_info = img_info + ('cluster_size: %s' % self.cluster_size,)
            if self.encrypted is not None:
                img_info = img_info + ('encrypted: %s' % self.encrypted,)
            if self.backing_file is not None:
                img_info = img_info + ('backing file: %s' %
                                       self.backing_file,)
        if self.garbage_before_snapshot is True:
            img_info = img_info + ('blah BLAH: bb',)
        if self.snapshot_count is not None:
            img_info = img_info + ('Snapshot list:',)
            img_info = img_info + ('ID        '
                                   'TAG                 '
                                   'VM SIZE                '
                                   'DATE       '
                                   'VM CLOCK',)
            for i in range(self.snapshot_count):
                img_info = img_info + ('%d        '
                    'd9a9784a500742a7bb95627bb3aace38    '
                    '0 2012-08-20 10:52:46 00:00:00.000' % (i + 1),)
        if self.garbage_before_snapshot is False:
            img_info = img_info + ('junk stuff: bbb',)
        example_output = '\n'.join(img_info)
        image_info = imageutils.QemuImgInfo(example_output)
        self.assertEqual(image_info.image, self.image_name)
        self.assertEqual(image_info.file_format, self.file_format)
        self.assertEqual(image_info.virtual_size, self.exp_virtual_size)
        self.assertEqual(image_info.disk_size, self.exp_disk_size)
        if self.snapshot_count is not None:
            self.assertEqual(len(image_info.snapshots), self.snapshot_count)
        if self.file_format == 'qcow2':
            self.assertEqual(image_info.cluster_size, self.exp_cluster_size)
            if self.backing_file is not None:
                self.assertEqual(image_info.backing_file,
                                 self.exp_backing_file)
            if self.encrypted is not None:
                self.assertEqual(image_info.encrypted, self.encrypted)

ImageUtilsTestCase.generate_scenarios()

class ImageUtilsTestCase2(test.BaseTestCase):
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

    def test_qemu_info_encrypted(self):
        path = 'disk.config'
        template_output = """image: %(path)s
file format: qcow2
virtual size: 2K (2048 bytes)
cluster_size: 65536
disk size: 96K
encrypted: yes
"""
        example_output = template_output % ({
            'path': path,
        })

        image_info = imageutils.QemuImgInfo(example_output)
        self.assertEqual('yes', image_info.encrypted,
                         "encrypted status must be 'yes'")

    def test_qemu_info_unencrypted(self):
        path = 'disk.config'
        template_output = """image: %(path)s
file format: qcow2
virtual size: 2K (2048 bytes)
cluster_size: 65536
disk size: 96K
"""
        example_output = template_output % ({
            'path': path,
        })

        image_info = imageutils.QemuImgInfo(example_output)
        self.assertIsNone(image_info.encrypted,
                          "encrypted status must be None")
