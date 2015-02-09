# Copyright 2014 Red Hat, Inc.
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

import base64
import gzip
import mock
import shutil
import tempfile


from oslo_concurrency import processutils
from oslotest import base as test_base
import requests
from testtools.matchers import HasLength

from openstack.common.libironic import disk_partitioner
from openstack.common.libironic import exception
from openstack.common.libironic import utils


class DiskPartitionerTestCase(test_base.BaseTestCase):

    def test_add_partition(self):
        dp = disk_partitioner.DiskPartitioner('/dev/fake')
        dp.add_partition(1024)
        dp.add_partition(512, fs_type='linux-swap')
        dp.add_partition(2048, bootable=True)
        expected = [(1, {'bootable': False,
                         'fs_type': '',
                         'type': 'primary',
                         'size': 1024}),
                    (2, {'bootable': False,
                         'fs_type': 'linux-swap',
                         'type': 'primary',
                         'size': 512}),
                    (3, {'bootable': True,
                         'fs_type': '',
                         'type': 'primary',
                         'size': 2048})]
        partitions = [(n, p) for n, p in dp.get_partitions()]
        self.assertThat(partitions, HasLength(3))
        self.assertEqual(expected, partitions)

    @mock.patch.object(disk_partitioner.DiskPartitioner, '_exec')
    @mock.patch.object(utils, 'execute')
    def test_commit(self, mock_utils_exc, mock_disk_partitioner_exec):
        dp = disk_partitioner.DiskPartitioner('/dev/fake')
        fake_parts = [(1, {'bootable': False,
                           'fs_type': 'fake-fs-type',
                           'type': 'fake-type',
                           'size': 1}),
                      (2, {'bootable': True,
                           'fs_type': 'fake-fs-type',
                           'type': 'fake-type',
                           'size': 1})]
        with mock.patch.object(dp, 'get_partitions') as mock_gp:
            mock_gp.return_value = fake_parts
            mock_utils_exc.return_value = (None, None)
            dp.commit()

        mock_disk_partitioner_exec.assert_called_once_with(
            'mklabel', 'msdos',
            'mkpart', 'fake-type', 'fake-fs-type', '1', '2',
            'mkpart', 'fake-type', 'fake-fs-type', '2', '3',
            'set', '2', 'boot', 'on')
        mock_utils_exc.assert_called_once_with(
            'fuser', '/dev/fake',
            run_as_root=True, check_exit_code=[0, 1])

    @mock.patch.object(disk_partitioner.DiskPartitioner, '_exec')
    @mock.patch.object(utils, 'execute')
    def test_commit_with_device_is_busy_once(self, mock_utils_exc,
                                             mock_disk_partitioner_exec):
        dp = disk_partitioner.DiskPartitioner('/dev/fake')
        fake_parts = [(1, {'bootable': False,
                           'fs_type': 'fake-fs-type',
                           'type': 'fake-type',
                           'size': 1}),
                      (2, {'bootable': True,
                           'fs_type': 'fake-fs-type',
                           'type': 'fake-type',
                           'size': 1})]
        fuser_outputs = [("/dev/fake: 10000 10001", None), (None, None)]

        with mock.patch.object(dp, 'get_partitions') as mock_gp:
            mock_gp.return_value = fake_parts
            mock_utils_exc.side_effect = fuser_outputs
            dp.commit()

        mock_disk_partitioner_exec.assert_called_once_with(
            'mklabel', 'msdos',
            'mkpart', 'fake-type', 'fake-fs-type', '1', '2',
            'mkpart', 'fake-type', 'fake-fs-type', '2', '3',
            'set', '2', 'boot', 'on')
        mock_utils_exc.assert_called_with(
            'fuser', '/dev/fake',
            run_as_root=True, check_exit_code=[0, 1])
        self.assertEqual(2, mock_utils_exc.call_count)

    @mock.patch.object(disk_partitioner.DiskPartitioner, '_exec')
    @mock.patch.object(utils, 'execute')
    def test_commit_with_device_is_always_busy(self, mock_utils_exc,
                                               mock_disk_partitioner_exec):
        dp = disk_partitioner.DiskPartitioner('/dev/fake')
        fake_parts = [(1, {'bootable': False,
                           'fs_type': 'fake-fs-type',
                           'type': 'fake-type',
                           'size': 1}),
                      (2, {'bootable': True,
                           'fs_type': 'fake-fs-type',
                           'type': 'fake-type',
                           'size': 1})]

        with mock.patch.object(dp, 'get_partitions') as mock_gp:
            mock_gp.return_value = fake_parts
            mock_utils_exc.return_value = ("/dev/fake: 10000 10001", None)
            self.assertRaises(exception.InstanceDeployFailure, dp.commit)

        mock_disk_partitioner_exec.assert_called_once_with(
            'mklabel', 'msdos',
            'mkpart', 'fake-type', 'fake-fs-type', '1', '2',
            'mkpart', 'fake-type', 'fake-fs-type', '2', '3',
            'set', '2', 'boot', 'on')
        mock_utils_exc.assert_called_with(
            'fuser', '/dev/fake',
            run_as_root=True, check_exit_code=[0, 1])
        self.assertEqual(20, mock_utils_exc.call_count)

    @mock.patch.object(disk_partitioner.DiskPartitioner, '_exec')
    @mock.patch.object(utils, 'execute')
    def test_commit_with_device_disconnected(self, mock_utils_exc,
                                             mock_disk_partitioner_exec):
        dp = disk_partitioner.DiskPartitioner('/dev/fake')
        fake_parts = [(1, {'bootable': False,
                           'fs_type': 'fake-fs-type',
                           'type': 'fake-type',
                           'size': 1}),
                      (2, {'bootable': True,
                           'fs_type': 'fake-fs-type',
                           'type': 'fake-type',
                           'size': 1})]

        with mock.patch.object(dp, 'get_partitions') as mock_gp:
            mock_gp.return_value = fake_parts
            mock_utils_exc.return_value = (None, "Specified filename /dev/fake"
                                                 " does not exist.")
            self.assertRaises(exception.InstanceDeployFailure, dp.commit)

        mock_disk_partitioner_exec.assert_called_once_with(
            'mklabel', 'msdos',
            'mkpart', 'fake-type', 'fake-fs-type', '1', '2',
            'mkpart', 'fake-type', 'fake-fs-type', '2', '3',
            'set', '2', 'boot', 'on')
        mock_utils_exc.assert_called_with(
            'fuser', '/dev/fake',
            run_as_root=True, check_exit_code=[0, 1])
        self.assertEqual(20, mock_utils_exc.call_count)


@mock.patch.object(utils, 'execute')
class ListPartitionsTestCase(test_base.BaseTestCase):

    def test_correct(self, execute_mock):
        output = """
BYT;
/dev/sda:500107862016B:scsi:512:4096:msdos:ATA HGST HTS725050A7:;
1:1.00MiB:501MiB:500MiB:ext4::boot;
2:501MiB:476940MiB:476439MiB:::;
"""
        expected = [
            {'start': 1, 'end': 501, 'size': 500,
             'filesystem': 'ext4', 'flags': 'boot'},
            {'start': 501, 'end': 476940, 'size': 476439,
             'filesystem': '', 'flags': ''},
        ]
        execute_mock.return_value = (output, '')
        result = disk_partitioner.list_partitions('/dev/fake')
        self.assertEqual(expected, result)
        execute_mock.assert_called_once_with(
            'parted', '-s', '-m', '/dev/fake', 'unit', 'MiB', 'print',
            use_standard_locale=True)

    @mock.patch.object(disk_partitioner.LOG, 'warn')
    def test_incorrect(self, log_mock, execute_mock):
        output = """
BYT;
/dev/sda:500107862016B:scsi:512:4096:msdos:ATA HGST HTS725050A7:;
1:XX1076MiB:---:524MiB:ext4::boot;
"""
        execute_mock.return_value = (output, '')
        self.assertEqual([], disk_partitioner.list_partitions('/dev/fake'))
        self.assertEqual(1, log_mock.call_count)


@mock.patch.object(disk_partitioner.DiskPartitioner, 'commit', lambda _: None)
class WorkOnDiskTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(WorkOnDiskTestCase, self).setUp()
        self.image_path = '/tmp/xyz/image'
        self.root_mb = 128
        self.swap_mb = 64
        self.ephemeral_mb = 0
        self.ephemeral_format = None
        self.configdrive_mb = 0
        self.dev = '/dev/fake'
        self.swap_part = '/dev/fake-part1'
        self.root_part = '/dev/fake-part2'

        self.mock_ibd = mock.patch.object(disk_partitioner,
                                          'is_block_device').start()
        self.mock_mp = mock.patch.object(disk_partitioner,
                                         'make_partitions').start()
        self.addCleanup(self.mock_ibd.stop)
        self.addCleanup(self.mock_mp.stop)
        self.mock_remlbl = mock.patch.object(disk_partitioner,
                                             'destroy_disk_metadata').start()
        self.addCleanup(self.mock_remlbl.stop)
        self.mock_mp.return_value = {'swap': self.swap_part,
                                     'root': self.root_part}

    def test_no_parent_device(self):
        self.mock_ibd.return_value = False
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_partitioner.work_on_disk, self.dev,
                          self.root_mb, self.swap_mb, self.ephemeral_mb,
                          self.ephemeral_format, self.image_path, False)
        self.mock_ibd.assert_called_once_with(self.dev)
        self.assertFalse(self.mock_mp.called,
                         "make_partitions mock was unexpectedly called.")

    def test_no_root_partition(self):
        self.mock_ibd.side_effect = [True, False]
        calls = [mock.call(self.dev),
                 mock.call(self.root_part)]
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_partitioner.work_on_disk, self.dev,
                          self.root_mb, self.swap_mb, self.ephemeral_mb,
                          self.ephemeral_format, self.image_path, False)
        self.assertEqual(self.mock_ibd.call_args_list, calls)
        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, self.ephemeral_mb,
                                             self.configdrive_mb, commit=True)

    def test_no_swap_partition(self):
        self.mock_ibd.side_effect = [True, True, False]
        calls = [mock.call(self.dev),
                 mock.call(self.root_part),
                 mock.call(self.swap_part)]
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_partitioner.work_on_disk, self.dev,
                          self.root_mb, self.swap_mb, self.ephemeral_mb,
                          self.ephemeral_format, self.image_path, False)
        self.assertEqual(self.mock_ibd.call_args_list, calls)
        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, self.ephemeral_mb,
                                             self.configdrive_mb, commit=True)

    def test_no_ephemeral_partition(self):
        ephemeral_part = '/dev/fake-part1'
        swap_part = '/dev/fake-part2'
        root_part = '/dev/fake-part3'
        ephemeral_mb = 256
        ephemeral_format = 'exttest'

        self.mock_mp.return_value = {'ephemeral': ephemeral_part,
                                     'swap': swap_part,
                                     'root': root_part}
        self.mock_ibd.side_effect = [True, True, True, False]
        calls = [mock.call(self.dev),
                 mock.call(root_part),
                 mock.call(swap_part),
                 mock.call(ephemeral_part)]
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_partitioner.work_on_disk, self.dev,
                          self.root_mb, self.swap_mb, ephemeral_mb,
                          ephemeral_format, self.image_path, False)
        self.assertEqual(self.mock_ibd.call_args_list, calls)
        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, ephemeral_mb,
                                             self.configdrive_mb, commit=True)

    @mock.patch.object(utils, 'unlink_without_raise')
    @mock.patch.object(disk_partitioner, '_get_configdrive')
    def test_no_configdrive_partition(self, mock_configdrive, mock_unlink):
        mock_configdrive.return_value = (10, 'fake-path')
        swap_part = '/dev/fake-part1'
        configdrive_part = '/dev/fake-part2'
        root_part = '/dev/fake-part3'
        configdrive_url = 'http://1.2.3.4/cd'
        configdrive_mb = 10

        self.mock_mp.return_value = {'swap': swap_part,
                                     'configdrive': configdrive_part,
                                     'root': root_part}
        self.mock_ibd.side_effect = [True, True, True, False]
        calls = [mock.call(self.dev),
                 mock.call(root_part),
                 mock.call(swap_part),
                 mock.call(configdrive_part)]
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_partitioner.work_on_disk, self.dev,
                          self.root_mb, self.swap_mb, self.ephemeral_mb,
                          self.ephemeral_format, self.image_path, 'fake-uuid',
                          preserve_ephemeral=False,
                          configdrive=configdrive_url)
        self.assertEqual(self.mock_ibd.call_args_list, calls)
        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, self.ephemeral_mb,
                                             configdrive_mb, commit=True)
        mock_unlink.assert_called_once_with('fake-path')


@mock.patch.object(utils, 'execute')
class MakePartitionsTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(MakePartitionsTestCase, self).setUp()
        self.dev = 'fake-dev'
        self.root_mb = 1024
        self.swap_mb = 512
        self.ephemeral_mb = 0
        self.configdrive_mb = 0
        self.parted_static_cmd = ['parted', '-a', 'optimal', '-s', self.dev,
                                  '--', 'unit', 'MiB', 'mklabel', 'msdos']

    def test_make_partitions(self, mock_exc):
        mock_exc.return_value = (None, None)
        disk_partitioner.make_partitions(self.dev, self.root_mb, self.swap_mb,
                                         self.ephemeral_mb,
                                         self.configdrive_mb)

        expected_mkpart = ['mkpart', 'primary', 'linux-swap', '1', '513',
                           'mkpart', 'primary', '', '513', '1537']
        parted_cmd = self.parted_static_cmd + expected_mkpart
        parted_call = mock.call(*parted_cmd, run_as_root=True,
                                check_exit_code=[0])
        fuser_cmd = ['fuser', 'fake-dev']
        fuser_call = mock.call(*fuser_cmd, run_as_root=True,
                               check_exit_code=[0, 1])
        mock_exc.assert_has_calls([parted_call, fuser_call])

    def test_make_partitions_with_ephemeral(self, mock_exc):
        self.ephemeral_mb = 2048
        expected_mkpart = ['mkpart', 'primary', '', '1', '2049',
                           'mkpart', 'primary', 'linux-swap', '2049', '2561',
                           'mkpart', 'primary', '', '2561', '3585']
        cmd = self.parted_static_cmd + expected_mkpart
        mock_exc.return_value = (None, None)
        disk_partitioner.make_partitions(self.dev, self.root_mb, self.swap_mb,
                                         self.ephemeral_mb,
                                         self.configdrive_mb)

        parted_call = mock.call(*cmd, run_as_root=True, check_exit_code=[0])
        mock_exc.assert_has_calls(parted_call)


@mock.patch.object(disk_partitioner, 'get_dev_block_size')
@mock.patch.object(utils, 'execute')
class DestroyMetaDataTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(DestroyMetaDataTestCase, self).setUp()
        self.dev = 'fake-dev'
        self.node_uuid = "12345678-1234-1234-1234-1234567890abcxyz"

    def test_destroy_disk_metadata(self, mock_exec, mock_gz):
        mock_gz.return_value = 64
        expected_calls = [mock.call('dd', 'if=/dev/zero', 'of=fake-dev',
                                    'bs=512', 'count=36', run_as_root=True,
                                    check_exit_code=[0]),
                          mock.call('dd', 'if=/dev/zero', 'of=fake-dev',
                                    'bs=512', 'count=36', 'seek=28',
                                    run_as_root=True,
                                    check_exit_code=[0])]
        disk_partitioner.destroy_disk_metadata(self.dev, self.node_uuid)
        mock_exec.assert_has_calls(expected_calls)
        self.assertTrue(mock_gz.called)

    def test_destroy_disk_metadata_get_dev_size_fail(self, mock_exec, mock_gz):
        mock_gz.side_effect = processutils.ProcessExecutionError

        expected_call = [mock.call('dd', 'if=/dev/zero', 'of=fake-dev',
                                   'bs=512', 'count=36', run_as_root=True,
                                   check_exit_code=[0])]
        self.assertRaises(processutils.ProcessExecutionError,
                          disk_partitioner.destroy_disk_metadata,
                          self.dev,
                          self.node_uuid)
        mock_exec.assert_has_calls(expected_call)

    def test_destroy_disk_metadata_dd_fail(self, mock_exec, mock_gz):
        mock_exec.side_effect = processutils.ProcessExecutionError

        expected_call = [mock.call('dd', 'if=/dev/zero', 'of=fake-dev',
                                   'bs=512', 'count=36', run_as_root=True,
                                   check_exit_code=[0])]
        self.assertRaises(processutils.ProcessExecutionError,
                          disk_partitioner.destroy_disk_metadata,
                          self.dev,
                          self.node_uuid)
        mock_exec.assert_has_calls(expected_call)
        self.assertFalse(mock_gz.called)


@mock.patch.object(utils, 'execute')
class GetDeviceBlockSizeTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(GetDeviceBlockSizeTestCase, self).setUp()
        self.dev = 'fake-dev'
        self.node_uuid = "12345678-1234-1234-1234-1234567890abcxyz"

    def test_get_dev_block_size(self, mock_exec):
        mock_exec.return_value = ("64", "")
        expected_call = [mock.call('blockdev', '--getsz', self.dev,
                                   run_as_root=True, check_exit_code=[0])]
        disk_partitioner.get_dev_block_size(self.dev)
        mock_exec.assert_has_calls(expected_call)


@mock.patch.object(disk_partitioner, 'dd')
@mock.patch.object(disk_partitioner, 'qemu_img_info')
@mock.patch.object(disk_partitioner, 'convert_image')
class PopulateImageTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(PopulateImageTestCase, self).setUp()

    def test_populate_raw_image(self, mock_cg, mock_qinfo, mock_dd):
        type(mock_qinfo.return_value).file_format = mock.PropertyMock(
            return_value='raw')
        disk_partitioner.populate_image('src', 'dst')
        mock_dd.assert_called_once_with('src', 'dst')
        self.assertFalse(mock_cg.called)

    def test_populate_qcow2_image(self, mock_cg, mock_qinfo, mock_dd):
        type(mock_qinfo.return_value).file_format = mock.PropertyMock(
            return_value='qcow2')
        disk_partitioner.populate_image('src', 'dst')
        mock_cg.assert_called_once_with('src', 'dst', 'raw', True)
        self.assertFalse(mock_dd.called)


@mock.patch.object(disk_partitioner, 'is_block_device', lambda d: True)
@mock.patch.object(disk_partitioner, 'block_uuid', lambda p: 'uuid')
@mock.patch.object(disk_partitioner, 'dd', lambda *_: None)
@mock.patch.object(disk_partitioner, 'convert_image', lambda *_: None)
@mock.patch.object(utils, 'mkfs', lambda *_: None)
# NOTE(dtantsur): destroy_disk_metadata resets file size, disabling it
@mock.patch.object(disk_partitioner, 'destroy_disk_metadata', lambda *_: None)
class RealFilePartitioningTestCase(test_base.BaseTestCase):
    """This test applies some real-world partitioning scenario to a file.

    This test covers the whole partitioning, mocking everything not possible
    on a file. That helps us assure, that we do all partitioning math properly
    and also conducts integration testing of DiskPartitioner.
    """

    def setUp(self):
        super(RealFilePartitioningTestCase, self).setUp()
        # NOTE(dtantsur): no parted utility on gate-ironic-python26
        try:
            utils.execute('parted', '--version')
        except OSError as exc:
            self.skipTest('parted utility was not found: %s' % exc)
        self.file = tempfile.NamedTemporaryFile(delete=False)
        # NOTE(ifarkas): the file needs to be closed, so fuser won't report
        #                any usage
        self.file.close()
        # NOTE(dtantsur): 20 MiB file with zeros
        utils.execute('dd', 'if=/dev/zero', 'of=%s' % self.file.name,
                      'bs=1', 'count=0', 'seek=20MiB')

    @staticmethod
    def _run_without_root(func, *args, **kwargs):
        """Make sure root is not required when using utils.execute."""
        real_execute = utils.execute

        def fake_execute(*cmd, **kwargs):
            kwargs['run_as_root'] = False
            return real_execute(*cmd, **kwargs)

        with mock.patch.object(utils, 'execute', fake_execute):
            return func(*args, **kwargs)

    def test_different_sizes(self):
        # NOTE(dtantsur): Keep this list in order with expected partitioning
        fields = ['ephemeral_mb', 'swap_mb', 'root_mb']
        variants = ((0, 0, 12), (4, 2, 8), (0, 4, 10), (5, 0, 10))
        for variant in variants:
            kwargs = dict(zip(fields, variant))
            self._run_without_root(disk_partitioner.work_on_disk,
                                   self.file.name, ephemeral_format='ext4',
                                   node_uuid='', image_path='path', **kwargs)
            part_table = self._run_without_root(
                disk_partitioner.list_partitions, self.file.name)
            for part, expected_size in zip(part_table, filter(None, variant)):
                self.assertEqual(expected_size, part['size'],
                                 "comparison failed for %s" % list(variant))

    def test_whole_disk(self):
        # 6 MiB ephemeral + 3 MiB swap + 9 MiB root + 1 MiB for MBR
        # + 1 MiB MAGIC == 20 MiB whole disk
        # TODO(dtantsur): figure out why we need 'magic' 1 more MiB
        # and why the is different on Ubuntu and Fedora (see below)
        self._run_without_root(disk_partitioner.work_on_disk, self.file.name,
                               root_mb=9, ephemeral_mb=6, swap_mb=3,
                               ephemeral_format='ext4', node_uuid='',
                               image_path='path')
        part_table = self._run_without_root(
            disk_partitioner.list_partitions, self.file.name)
        sizes = [part['size'] for part in part_table]
        # NOTE(dtantsur): parted in Ubuntu 12.04 will occupy the last MiB,
        # parted in Fedora 20 won't - thus two possible variants for last part
        self.assertEqual([6, 3], sizes[:2],
                         "unexpected partitioning %s" % part_table)
        self.assertIn(sizes[2], (9, 10))


@mock.patch.object(shutil, 'copyfileobj')
@mock.patch.object(requests, 'get')
class GetConfigdriveTestCase(test_base.BaseTestCase):

    @mock.patch.object(gzip, 'GzipFile')
    def test_get_configdrive(self, mock_gzip, mock_requests, mock_copy):
        mock_requests.return_value = mock.MagicMock(content='Zm9vYmFy')
        disk_partitioner._get_configdrive('http://1.2.3.4/cd',
                                          'fake-node-uuid')
        mock_requests.assert_called_once_with('http://1.2.3.4/cd')
        mock_gzip.assert_called_once_with('configdrive', 'rb',
                                          fileobj=mock.ANY)
        mock_copy.assert_called_once_with(mock.ANY, mock.ANY)

    @mock.patch.object(gzip, 'GzipFile')
    def test_get_configdrive_base64_string(self, mock_gzip, mock_requests,
                                           mock_copy):
        disk_partitioner._get_configdrive('Zm9vYmFy', 'fake-node-uuid')
        self.assertFalse(mock_requests.called)
        mock_gzip.assert_called_once_with('configdrive', 'rb',
                                          fileobj=mock.ANY)
        mock_copy.assert_called_once_with(mock.ANY, mock.ANY)

    def test_get_configdrive_bad_url(self, mock_requests, mock_copy):
        mock_requests.side_effect = requests.exceptions.RequestException
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_partitioner._get_configdrive,
                          'http://1.2.3.4/cd', 'fake-node-uuid')
        self.assertFalse(mock_copy.called)

    @mock.patch.object(base64, 'b64decode')
    def test_get_configdrive_base64_error(self, mock_b64, mock_requests,
                                          mock_copy):
        mock_b64.side_effect = TypeError
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_partitioner._get_configdrive,
                          'malformed', 'fake-node-uuid')
        mock_b64.assert_called_once_with('malformed')
        self.assertFalse(mock_copy.called)

    @mock.patch.object(gzip, 'GzipFile')
    def test_get_configdrive_gzip_error(self, mock_gzip, mock_requests,
                                        mock_copy):
        mock_requests.return_value = mock.MagicMock(content='Zm9vYmFy')
        mock_copy.side_effect = IOError
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_partitioner._get_configdrive,
                          'http://1.2.3.4/cd', 'fake-node-uuid')
        mock_requests.assert_called_once_with('http://1.2.3.4/cd')
        mock_gzip.assert_called_once_with('configdrive', 'rb',
                                          fileobj=mock.ANY)
        mock_copy.assert_called_once_with(mock.ANY, mock.ANY)
