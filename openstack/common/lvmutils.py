# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2010 United States Government as represented by the
#    Administrator of the National Aeronautics and Space Administration.
#    All Rights Reserved.
#    Copyright (c) 2010 Citrix Systems, Inc.
#    Copyright (c) 2011 Piston Cloud Computing, Inc
#    Copyright (c) 2011 OpenStack Foundation
#    (c) Copyright 2013 Hewlett-Packard Development Company, L.P.
#    Copyright (c) 2013 Rackspace Australia
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

from openstack.common.gettextutils import _  # noqa
from openstack.common import log as logging
from openstack.common import processutils


LOG = logging.getLogger(__name__)


def get_volume_group_info(vg, root_helper):
    """Return free/used/total space info for a volume group in bytes

    :param vg: volume group name
    :returns: A dict containing:
             :total: How big the filesystem is (in bytes)
             :free: How much space is free (in bytes)
             :used: How much space is used (in bytes)
    """

    out, _err = processutils.execute('vgs', '--noheadings', '--nosuffix',
                                     '--separator', '|', '--units', 'b', '-o',
                                     'vg_size,vg_free', vg, run_as_root=True,
                                     root_helper=root_helper)

    try:
        total, free = map(int, out.split('|'))
    except ValueError:
        raise RuntimeError(_("vg %s must be LVM volume group") % vg)

    return {'total': total,
            'free': free,
            'used': total-free}


def create_logical_volume(vg, lv, size, root_helper, sparse=False):
    """Create a logical volume with the given size.

    :param vg: existing volume group which should hold this image
    :param lv: name for this image (logical volume)
    :size: size of image in bytes
    :sparse: create sparse logical volume
    """
    vg_info = get_volume_group_info(vg, root_helper)
    free_space = vg_info['free']

    def check_size(vg, lv, size):
        if size > free_space:
            raise RuntimeError(_('Insufficient Space on Volume Group %(vg)s.'
                                 ' Only %(free_space)db available,'
                                 ' but %(size)db required'
                                 ' by volume %(lv)s.') %
                               {'vg': vg,
                                'free_space': free_space,
                                'size': size,
                                'lv': lv})

    if sparse:
        preallocated_space = 64 * 1024 * 1024
        check_size(vg, lv, preallocated_space)
        if free_space < size:
            LOG.warning(_('Volume group %(vg)s will not be able'
                          ' to hold sparse volume %(lv)s.'
                          ' Virtual volume size is %(size)db,'
                          ' but free space on volume group is'
                          ' only %(free_space)db.'),
                        {'vg': vg,
                         'free_space': free_space,
                         'size': size,
                         'lv': lv})

        cmd = ('lvcreate', '-L', '%db' % preallocated_space,
               '--virtualsize', '%db' % size, '-n', lv, vg)
    else:
        check_size(vg, lv, size)
        cmd = ('lvcreate', '-L', '%db' % size, '-n', lv, vg)
    processutils.execute(*cmd, run_as_root=True, root_helper=root_helper,
                         attempts=3)


def list_logical_volumes(vg, root_helper):
    """List logical volumes paths for given volume group.

    :param vg: volume group name
    """
    out, err = processutils.execute('lvs', '--noheadings', '-o', 'lv_name', vg,
                                    root_helper=root_helper, run_as_root=True)

    return [line.strip() for line in out.splitlines()]


def logical_volume_info(path, root_helper):
    """Get logical volume info.

    :param path: logical volume path
    """
    out, err = processutils.execute('lvs', '-o', 'vg_all,lv_all',
                                    '--separator', '|', path,
                                    root_helper=root_helper,
                                    run_as_root=True)

    info = [line.split('|') for line in out.splitlines()]

    if len(info) != 2:
        raise RuntimeError(_("Path %s must be LVM logical volume") % path)

    return dict(zip(*info))


def logical_volume_size(path, root_helper):
    """Get logical volume size in bytes.

    :param path: logical volume path
    """
    # TODO(p-draigbrady) Possibly replace with the more general
    # use of blockdev --getsize64 in future
    out, _err = processutils.execute('lvs', '-o', 'lv_size', '--noheadings',
                                     '--units', 'b', '--nosuffix', path,
                                     root_helper=root_helper, run_as_root=True)

    return int(out)


def clear_logical_volume(path, root_helper):
    """Obfuscate the logical volume.

    :param path: logical volume path
    """
    # TODO(p-draigbrady): We currently overwrite with zeros
    # but we may want to make this configurable in future
    # for more or less security conscious setups.

    vol_size = logical_volume_size(path, root_helper)
    bs = 1024 * 1024
    direct_flags = ('oflag=direct',)
    sync_flags = ()
    remaining_bytes = vol_size

    # The loop caters for versions of dd that
    # don't support the iflag=count_bytes option.
    while remaining_bytes:
        zero_blocks = remaining_bytes / bs
        seek_blocks = (vol_size - remaining_bytes) / bs
        zero_cmd = ('dd', 'bs=%s' % bs,
                    'if=/dev/zero', 'of=%s' % path,
                    'seek=%s' % seek_blocks, 'count=%s' % zero_blocks)
        zero_cmd += direct_flags
        zero_cmd += sync_flags
        if zero_blocks:
            processutils.execute(*zero_cmd, root_helper=root_helper,
                                 run_as_root=True)
        remaining_bytes %= bs
        bs /= 1024  # Limit to 3 iterations
        # Use O_DIRECT with initial block size and fdatasync otherwise
        direct_flags = ()
        sync_flags = ('conv=fdatasync',)


def remove_logical_volume(paths, root_helper):
    """Remove one or more logical volume."""

    for path in paths:
        clear_logical_volume(path, root_helper)

    if paths:
        lvremove = ['lvremove', '-f'] + paths
        processutils.execute(*lvremove, attempts=3, root_helper=root_helper,
                             run_as_root=True)
