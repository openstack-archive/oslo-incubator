# vim: tabstop=4 shiftwidth=4 softtabstop=4

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
import math
import re

from openstack.common import log as logging
from openstack.common import process_utils as putils
from openstack.common import uuidutils


LOG = logging.getLogger(__name__)


class physical_volume():
    def __init__(self, **kwargs):
        self.uuid = kwargs.pop('uuid', uuidutils.generate_uuid())
        self.device_list = kwargs.pop('device_list', None)
        self.volume_group_ids = []

    def remove_volume_group(self, vg_id):
        if vg_id in self.volume_group_ids:
            self.volume_group_ids = filter(lambda a: a != vg_id,
                                           self.volume_group_ids)

    def add_volume_group(self, vg_id):
        if vg_id not in self.volume_group_ids:
            self.volume_group_ids.append(vg_id)

    def create(self, device_list=None, name=None):
        cmd = ['pvcreate']
        if device_list is None:
            if self._device_list is None:
                LOG.error('No devices supplied for PV group')
                raise
            else:
                device_list = self._device_list()

        cmd.extend(device_list)
        (out, err) = putils.execute(*cmd, run_as_root=True)


class volume_group():
    def __init__(self, pv_ref_list, name=None, **kwargs):
        self.uuid = kwargs.pop('uuid', uuidutils.generate_uuid())
        self.pv_refs = pv_ref_list
        self.name = name
        if name is None:
            self.name = self.uuid

    def create(self):
        pv_list = []
        for pv in self.pv_refs:
            pv_list.extend(pv.device_list())

        cmd = ['vgcreate', self.name]
        cmd.extend(pv_list)
        (out, err) = putils.execute(*cmd, run_as_root=True)

        for pv in self.pv_refs:
            pv.add_volume_group(self.uuid)

    def extend(self, pv_refs):
        pv_list = []
        for pv in pv_refs:
            self.pv_refs.append(pv)
            pv_list.extend(pv.device_list())

        cmd = ['vgextend', self.name]
        cmd.extend(pv_list)
        (out, err) = putils.execute(*cmd, run_as_root=True)

    def remove(self, force=False):
        cmd = ['vgremove']
        if force:
            cmd.append('--force')
        (out, err) = putils.execute(*cmd, run_as_root=True)


class logical_volume():
    def __init__(self, vg_ref, name=None, type=None, **kwargs):
        self.vg_ref = vg_ref
        self.uuid = kwargs.pop('uuid', uuidutils.generate_uuid())
        self.size = kwargs.pop('size', None)
        self.mirror_count = kwargs.pop('mirror_count', 0)
        self.pool_size = kwargs.pop('pool_size', 0)
        self.pool_name = None
        self.type = type

        self.name = name
        if name is None:
            self.name = self.uuid
        self.name = self.name.lower()

        if type is not None and type.lower() == 'thin':
            self.type = 'thin'
            self._create_thin_pool(self.pool_size, vg_ref, self.name)

    def _volume_is_present(self):
        return True

    def _create_thin_pool(self, pool_size, vg_ref, name):
        (out, err) = putils.execute('lvs', '--option',
                                    'name', '--noheadings',
                                    run_as_root=True)

        pool_name = "%s-pool" % vg_ref.name
        if pool_name not in out:
            if pool_size == 0:
                out, err = self._execute('vgs', vg_ref.name,
                                         '--noheadings', '--options',
                                         'name,size',
                                         run_as_root=True)
                size = re.sub(r'[\.][\d][\d]', '', out.split()[1])
            else:
                size = "%s" % pool_size

            pool_path = '%s/%s' % (vg_ref.name, pool_name)
            (out, err) = self._execute('lvcreate', '-T', '-L', size,
                                       pool_path, run_as_root=True)
            self.pool_path = pool_path

    def create(self, size, **kwargs):
        cmd = ['lvcreate', '-n', self.name, self.vg_ref.name]
        if self.type == 'thin':
            cmd += ['-T', '-V', self._sizestr(self.size)]
        else:
            cmd += ['-L', self._sizestr(self.size)]

        if self.mirror_count > 0:
            cmd += ['-m', self.mirror_count, '--nosync']
            terras = int(self.size[:-1]) / 1024.0
            if terras >= 1.5:
                rsize = int(2 ** math.ceil(math.log(terras) / math.log(2)))
                # NOTE(vish): Next power of two for region size. See:
                #             http://red.ht/U2BPOD
                cmd += ['-R', str(rsize)]

        (out, err) = putils.execute(*cmd, run_as_root=True)
    def remove(self, force=False):
        if not self._volume_is_present():
            return True
        (out, err) = putils.execute('lvremove', '-f', '%s/%s' % self.vg_ref.name
        self._try_execute('lvremove', '-f', "%s/%s" %
                          (FLAGS.volume_group,
                           self._escape_snapshot(volume['name'])),
                          run_as_root=True)
