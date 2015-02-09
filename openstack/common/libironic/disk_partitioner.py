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
import logging
import math
import os
import re
import requests
import shutil
import six
import stat
import tempfile

from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_utils import excutils
from oslo_utils import units

from openstack.common._i18n import _
from openstack.common._i18n import _LE
from openstack.common._i18n import _LW
from openstack.common import imageutils
from openstack.common import loopingcall

from openstack.common.libironic import exception
from openstack.common.libironic import utils


opts = [
    cfg.IntOpt('check_device_interval',
               default=1,
               help='After Ironic has completed creating the partition table, '
                    'it continues to check for activity on the attached iSCSI '
                    'device status at this interval prior to copying the image'
                    ' to the node, in seconds'),
    cfg.IntOpt('check_device_max_retries',
               default=20,
               help='The maximum number of times to check that the device is '
                    'not accessed by another process. If the device is still '
                    'busy after that, the disk partitioning will be treated as'
                    ' having failed.'),
]

CONF = cfg.CONF
opt_group = cfg.OptGroup(name='disk_partitioner',
                         title='Options for the disk partitioner')
CONF.register_group(opt_group)
CONF.register_opts(opts, opt_group)

LOG = logging.getLogger(__name__)


class DiskPartitioner(object):

    def __init__(self, device, disk_label='msdos', alignment='optimal'):
        """A convenient wrapper around the parted tool.

        :param device: The device path.
        :param disk_label: The type of the partition table. Valid types are:
                           "bsd", "dvh", "gpt", "loop", "mac", "msdos",
                           "pc98", or "sun".
        :param alignment: Set alignment for newly created partitions.
                          Valid types are: none, cylinder, minimal and
                          optimal.

        """
        self._device = device
        self._disk_label = disk_label
        self._alignment = alignment
        self._partitions = []
        self._fuser_pids_re = re.compile(r'((\d)+\s*)+')

    def _exec(self, *args):
        # NOTE(lucasagomes): utils.execute() is already a wrapper on top
        #                    of processutils.execute() which raises specific
        #                    exceptions. It also logs any failure so we don't
        #                    need to log it again here.
        utils.execute('parted', '-a', self._alignment, '-s', self._device,
                      '--', 'unit', 'MiB', *args, check_exit_code=[0],
                      run_as_root=True)

    def add_partition(self, size, part_type='primary', fs_type='',
                      bootable=False):
        """Add a partition.

        :param size: The size of the partition in MiB.
        :param part_type: The type of the partition. Valid values are:
                          primary, logical, or extended.
        :param fs_type: The filesystem type. Valid types are: ext2, fat32,
                        fat16, HFS, linux-swap, NTFS, reiserfs, ufs.
                        If blank (''), it will create a Linux native
                        partition (83).
        :param bootable: Boolean value; whether the partition is bootable
                         or not.
        :returns: The partition number.

        """
        self._partitions.append({'size': size,
                                 'type': part_type,
                                 'fs_type': fs_type,
                                 'bootable': bootable})
        return len(self._partitions)

    def get_partitions(self):
        """Get the partitioning layout.

        :returns: An iterator with the partition number and the
                  partition layout.

        """
        return enumerate(self._partitions, 1)

    def _wait_for_disk_to_become_available(self, retries, max_retries, pids,
                                           stderr):
        retries[0] += 1
        if retries[0] > max_retries:
            raise loopingcall.LoopingCallDone()

        try:
            # NOTE(ifarkas): fuser returns a non-zero return code if none of
            #                the specified files is accessed
            out, err = utils.execute('fuser', self._device,
                                     check_exit_code=[0, 1], run_as_root=True)

            if not out and not err:
                raise loopingcall.LoopingCallDone()
            else:
                if err:
                    stderr[0] = err
                if out:
                    pids_match = re.search(self._fuser_pids_re, out)
                    pids[0] = pids_match.group()
        except processutils.ProcessExecutionError as exc:
            LOG.warning(_LW('Failed to check the device %(device)s with fuser:'
                            ' %(err)s'), {'device': self._device, 'err': exc})

    def commit(self):
        """Write to the disk."""
        LOG.debug("Committing partitions to disk.")
        cmd_args = ['mklabel', self._disk_label]
        # NOTE(lucasagomes): Lead in with 1MiB to allow room for the
        #                    partition table itself.
        start = 1
        for num, part in self.get_partitions():
            end = start + part['size']
            cmd_args.extend(['mkpart', part['type'], part['fs_type'],
                             str(start), str(end)])
            if part['bootable']:
                cmd_args.extend(['set', str(num), 'boot', 'on'])
            start = end

        self._exec(*cmd_args)

        retries = [0]
        pids = ['']
        fuser_err = ['']
        interval = CONF.disk_partitioner.check_device_interval
        max_retries = CONF.disk_partitioner.check_device_max_retries

        timer = loopingcall.FixedIntervalLoopingCall(
            self._wait_for_disk_to_become_available,
            retries, max_retries, pids, fuser_err)
        timer.start(interval=interval).wait()

        if retries[0] > max_retries:
            if pids[0]:
                raise exception.InstanceDeployFailure(
                    _('Disk partitioning failed on device %(device)s. '
                      'Processes with the following PIDs are holding it: '
                      '%(pids)s. Time out waiting for completion.')
                    % {'device': self._device, 'pids': pids[0]})
            else:
                raise exception.InstanceDeployFailure(
                    _('Disk partitioning failed on device %(device)s. Fuser '
                      'exited with "%(fuser_err)s". Time out waiting for '
                      'completion.')
                    % {'device': self._device, 'fuser_err': fuser_err[0]})


_PARTED_PRINT_RE = re.compile(r"^\d+:([\d\.]+)MiB:"
                              "([\d\.]+)MiB:([\d\.]+)MiB:(\w*)::(\w*)")


def list_partitions(device):
    """Get partitions information from given device.

    :param device: The device path.
    :returns: list of dictionaries (one per partition) with keys:
              start, end, size (in MiB), filesystem, flags
    """
    output = utils.execute(
        'parted', '-s', '-m', device, 'unit', 'MiB', 'print',
        use_standard_locale=True)[0]
    lines = [line for line in output.split('\n') if line.strip()][2:]
    # Example of line: 1:1.00MiB:501MiB:500MiB:ext4::boot
    fields = ('start', 'end', 'size', 'filesystem', 'flags')
    result = []
    for line in lines:
        match = _PARTED_PRINT_RE.match(line)
        if match is None:
            LOG.warn(_LW("Partition information from parted for device "
                         "%(device)s does not match "
                         "expected format: %(line)s"),
                     dict(device=device, line=line))
            continue
        # Cast int fields to ints (some are floats and we round them down)
        groups = [int(float(x)) if i < 3 else x
                  for i, x in enumerate(match.groups())]
        result.append(dict(zip(fields, groups)))
    return result


def make_partitions(dev, root_mb, swap_mb, ephemeral_mb,
                    configdrive_mb, commit=True):
    """Partition the disk device.

    Create partitions for root, swap, ephemeral and configdrive on a
    disk device.

    :param root_mb: Size of the root partition in mebibytes (MiB).
    :param swap_mb: Size of the swap partition in mebibytes (MiB). If 0,
        no partition will be created.
    :param ephemeral_mb: Size of the ephemeral partition in mebibytes (MiB).
        If 0, no partition will be created.
    :param configdrive_mb: Size of the configdrive partition in
        mebibytes (MiB). If 0, no partition will be created.
    :param commit: True/False. Default for this setting is True. If False
        partitions will not be written to disk.
    :returns: A dictionary containing the partition type as Key and partition
        path as Value for the partitions created by this method.

    """
    LOG.debug("Starting to partition the disk device: %(dev)s",
              {'dev': dev})
    part_template = dev + '-part%d'
    part_dict = {}
    dp = DiskPartitioner(dev)
    if ephemeral_mb:
        LOG.debug("Add ephemeral partition (%(size)d MB) to device: %(dev)s",
                  {'dev': dev, 'size': ephemeral_mb})
        part_num = dp.add_partition(ephemeral_mb)
        part_dict['ephemeral'] = part_template % part_num
    if swap_mb:
        LOG.debug("Add Swap partition (%(size)d MB) to device: %(dev)s",
                  {'dev': dev, 'size': swap_mb})
        part_num = dp.add_partition(swap_mb, fs_type='linux-swap')
        part_dict['swap'] = part_template % part_num
    if configdrive_mb:
        LOG.debug("Add config drive partition (%(size)d MB) to device: "
                  "%(dev)s", {'dev': dev, 'size': configdrive_mb})
        part_num = dp.add_partition(configdrive_mb)
        part_dict['configdrive'] = part_template % part_num

    # NOTE(lucasagomes): Make the root partition the last partition. This
    # enables tools like cloud-init's growroot utility to expand the root
    # partition until the end of the disk.
    LOG.debug("Add root partition (%(size)d MB) to device: %(dev)s",
              {'dev': dev, 'size': root_mb})
    part_num = dp.add_partition(root_mb)
    part_dict['root'] = part_template % part_num

    if commit:
        # write to the disk
        dp.commit()
    return part_dict


def dd(src, dst):
    """Execute dd from src to dst."""
    utils.dd(src, dst, 'bs=%s' % CONF.deploy.dd_block_size, 'oflag=direct')


def qemu_img_info(path):
    """Return an object containing the parsed output from qemu-img info."""
    if not os.path.exists(path):
        return imageutils.QemuImgInfo()

    out, err = utils.execute('env', 'LC_ALL=C', 'LANG=C',
                             'qemu-img', 'info', path)
    return imageutils.QemuImgInfo(out)


def convert_image(source, dest, out_format, run_as_root=False):
    """Convert image to other format."""
    cmd = ('qemu-img', 'convert', '-O', out_format, source, dest)
    utils.execute(*cmd, run_as_root=run_as_root)


def populate_image(src, dst):
    data = qemu_img_info(src)
    if data.file_format == 'raw':
        dd(src, dst)
    else:
        convert_image(src, dst, 'raw', True)


def is_block_device(dev):
    """Check whether a device is block or not."""
    s = os.stat(dev)
    return stat.S_ISBLK(s.st_mode)


def mkswap(dev, label='swap1'):
    """Execute mkswap on a device."""
    utils.mkfs('swap', dev, label)


def mkfs_ephemeral(dev, ephemeral_format, label="ephemeral0"):
    utils.mkfs(ephemeral_format, dev, label)


def block_uuid(dev):
    """Get UUID of a block device."""
    out, _err = utils.execute('blkid', '-s', 'UUID', '-o', 'value', dev,
                              run_as_root=True,
                              check_exit_code=[0])
    return out.strip()


def get_dev_block_size(dev):
    """Get the device size in 512 byte sectors."""
    block_sz, cmderr = utils.execute('blockdev', '--getsz', dev,
                                     run_as_root=True, check_exit_code=[0])
    return int(block_sz)


def destroy_disk_metadata(dev, node_uuid):
    """Destroy metadata structures on node's disk.

       Ensure that node's disk appears to be blank without zeroing the entire
       drive. To do this we will zero:
       - the first 18KiB to clear MBR / GPT data
       - the last 18KiB to clear GPT and other metadata like: LVM, veritas,
         MDADM, DMRAID, ...
    """
    # NOTE(NobodyCam): This is needed to work around bug:
    # https://bugs.launchpad.net/ironic/+bug/1317647
    LOG.debug("Start destroy disk metadata for node %(node)s.",
              {'node': node_uuid})
    try:
        utils.execute('dd', 'if=/dev/zero', 'of=%s' % dev,
                      'bs=512', 'count=36', run_as_root=True,
                      check_exit_code=[0])
    except processutils.ProcessExecutionError as err:
        with excutils.save_and_reraise_exception():
            LOG.error(_LE("Failed to erase beginning of disk for node "
                          "%(node)s. Command: %(command)s. Error: %(error)s."),
                      {'node': node_uuid,
                       'command': err.cmd,
                       'error': err.stderr})

    # now wipe the end of the disk.
    # get end of disk seek value
    try:
        block_sz = get_dev_block_size(dev)
    except processutils.ProcessExecutionError as err:
        with excutils.save_and_reraise_exception():
            LOG.error(_LE("Failed to get disk block count for node %(node)s. "
                          "Command: %(command)s. Error: %(error)s."),
                      {'node': node_uuid,
                       'command': err.cmd,
                       'error': err.stderr})
    else:
        seek_value = block_sz - 36
        try:
            utils.execute('dd', 'if=/dev/zero', 'of=%s' % dev,
                          'bs=512', 'count=36', 'seek=%d' % seek_value,
                          run_as_root=True, check_exit_code=[0])
        except processutils.ProcessExecutionError as err:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Failed to erase the end of the disk on node "
                              "%(node)s. Command: %(command)s. "
                              "Error: %(error)s."),
                          {'node': node_uuid,
                           'command': err.cmd,
                           'error': err.stderr})


def _get_configdrive(configdrive, node_uuid):
    """Get the information about size and location of the configdrive.

    :param configdrive: Base64 encoded Gzipped configdrive content or
        configdrive HTTP URL.
    :param node_uuid: Node's uuid. Used for logging.
    :raises: InstanceDeployFailure if it can't download or decode the
       config drive.
    :returns: A tuple with the size in MiB and path to the uncompressed
        configdrive file.

    """
    # Check if the configdrive option is a HTTP URL or the content directly
    is_url = utils.is_http_url(configdrive)
    if is_url:
        try:
            data = requests.get(configdrive).content
        except requests.exceptions.RequestException as e:
            raise exception.InstanceDeployFailure(
                _("Can't download the configdrive content for node %(node)s "
                  "from '%(url)s'. Reason: %(reason)s") %
                {'node': node_uuid, 'url': configdrive, 'reason': e})
    else:
        data = configdrive

    try:
        data = six.StringIO(base64.b64decode(data))
    except TypeError:
        error_msg = (_('Config drive for node %s is not base64 encoded '
                       'or the content is malformed.') % node_uuid)
        if is_url:
            error_msg += _(' Downloaded from "%s".') % configdrive
        raise exception.InstanceDeployFailure(error_msg)

    configdrive_file = tempfile.NamedTemporaryFile(delete=False,
                                                   prefix='configdrive')
    configdrive_mb = 0
    with gzip.GzipFile('configdrive', 'rb', fileobj=data) as gunzipped:
        try:
            shutil.copyfileobj(gunzipped, configdrive_file)
        except EnvironmentError as e:
            # Delete the created file
            utils.unlink_without_raise(configdrive_file.name)
            raise exception.InstanceDeployFailure(
                _('Encountered error while decompressing and writing '
                  'config drive for node %(node)s. Error: %(exc)s') %
                {'node': node_uuid, 'exc': e})
        else:
            # Get the file size and convert to MiB
            configdrive_file.seek(0, os.SEEK_END)
            bytes_ = configdrive_file.tell()
            configdrive_mb = int(math.ceil(float(bytes_) / units.Mi))
        finally:
            configdrive_file.close()

        return (configdrive_mb, configdrive_file.name)


def work_on_disk(dev, root_mb, swap_mb, ephemeral_mb, ephemeral_format,
                 image_path, node_uuid, preserve_ephemeral=False,
                 configdrive=None):
    """Create partitions and copy an image to the root partition.

    :param dev: Path for the device to work on.
    :param root_mb: Size of the root partition in megabytes.
    :param swap_mb: Size of the swap partition in megabytes.
    :param ephemeral_mb: Size of the ephemeral partition in megabytes. If 0,
        no ephemeral partition will be created.
    :param ephemeral_format: The type of file system to format the ephemeral
        partition.
    :param image_path: Path for the instance's disk image.
    :param node_uuid: node's uuid. Used for logging.
    :param preserve_ephemeral: If True, no filesystem is written to the
        ephemeral block device, preserving whatever content it had (if the
        partition table has not changed).
    :param configdrive: Optional. Base64 encoded Gzipped configdrive content
                        or configdrive HTTP URL.
    :returns: the UUID of the root partition.
    """
    if not is_block_device(dev):
        raise exception.InstanceDeployFailure(
            _("Parent device '%s' not found") % dev)

    # the only way for preserve_ephemeral to be set to true is if we are
    # rebuilding an instance with --preserve_ephemeral.
    commit = not preserve_ephemeral
    # now if we are committing the changes to disk clean first.
    if commit:
        destroy_disk_metadata(dev, node_uuid)

    try:
        # If requested, get the configdrive file and determine the size
        # of the configdrive partition
        configdrive_mb = 0
        configdrive_file = None
        if configdrive:
            configdrive_mb, configdrive_file = _get_configdrive(configdrive,
                                                                node_uuid)

        part_dict = make_partitions(dev, root_mb, swap_mb, ephemeral_mb,
                                    configdrive_mb, commit=commit)

        ephemeral_part = part_dict.get('ephemeral')
        swap_part = part_dict.get('swap')
        configdrive_part = part_dict.get('configdrive')
        root_part = part_dict.get('root')

        if not is_block_device(root_part):
            raise exception.InstanceDeployFailure(
                _("Root device '%s' not found") % root_part)

        for part in ('swap', 'ephemeral', 'configdrive'):
            part_device = part_dict.get(part)
            LOG.debug("Checking for %(part)s device (%(dev)s) on node "
                      "%(node)s.", {'part': part, 'dev': part_device,
                                    'node': node_uuid})
            if part_device and not is_block_device(part_device):
                raise exception.InstanceDeployFailure(
                    _("'%(partition)s' device '%(part_device)s' not found") %
                    {'partition': part, 'part_device': part_device})

        if configdrive_part:
            # Copy the configdrive content to the configdrive partition
            dd(configdrive_file, configdrive_part)

    finally:
        # If the configdrive was requested make sure we delete the file
        # after copying the content to the partition
        if configdrive_file:
            utils.unlink_without_raise(configdrive_file)

    populate_image(image_path, root_part)

    if swap_part:
        mkswap(swap_part)

    if ephemeral_part and not preserve_ephemeral:
        mkfs_ephemeral(ephemeral_part, ephemeral_format)

    try:
        root_uuid = block_uuid(root_part)
    except processutils.ProcessExecutionError:
        with excutils.save_and_reraise_exception():
            LOG.error(_LE("Failed to detect root device UUID."))

    return root_uuid
