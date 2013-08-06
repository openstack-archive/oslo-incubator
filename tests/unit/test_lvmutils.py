# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2013 Rackspace Australia
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

import fixtures

from openstack.common import lvmutils
from tests import utils


class TestLvmUtils(utils.BaseTestCase):
    def test_get_volume_group_info_correct(self):
        # vgs output looks like this:
        # $ sudo vgs --noheadings --nosuffix --separator '|' --units b \
        #   -o "vg_size,vg_free" raidvg
        # 5000449228800|5293211648

        def fake_execute(*cmd, **kwargs):
            return '5000449228800|5293211648', ''

        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute))

        info = lvmutils.get_volume_group_info('foo', 'fake_helper')
        self.assertEqual(5000449228800, info['total'])
        self.assertEqual(5293211648, info['free'])
        self.assertEqual(5000449228800 - 5293211648, info['used'])

    def test_get_volume_group_info_bad_output(self):
        def fake_execute(*cmd, **kwargs):
            return '5000449228800|5293211648|gerkin', ''

        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute))

        self.assertRaises(RuntimeError, lvmutils.get_volume_group_info, 'foo',
                          'fake_helper')

    def test_create_logical_volume_dense(self):
        cmd = []

        def fake_get_volume_group_info(path, root_helper):
            return {'free': 4200}

        def fake_execute(*args, **kwargs):
            for arg in args:
                cmd.append(arg)
            for key in kwargs:
                cmd.append('%s=%s' % (key, kwargs[key]))

        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.lvmutils.get_volume_group_info',
            fake_get_volume_group_info))
        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute))

        lvmutils.create_logical_volume('foo', 'bar', 4000, 'fake_helper',
                                       sparse=False)
        self.assertEqual(['lvcreate', '-L', '4000b', '-n', 'bar', 'foo',
                          'attempts=3', 'root_helper=fake_helper',
                          'run_as_root=True'], cmd)

    def test_create_logical_volume_no_space_dense(self):
        def fake_get_volume_group_info(*args):
            return {'free': 42}

        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.lvmutils.get_volume_group_info',
            fake_get_volume_group_info))

        self.assertRaises(RuntimeError, lvmutils.create_logical_volume,
                          'foo', 'bar', 4000, 'fake_helper', sparse=False)

    def test_create_logical_volume_sparse(self):
        cmd = []

        def fake_get_volume_group_info(path, root_helper):
            return {'free': 65 * 1024 * 1024}

        def fake_execute(*args, **kwargs):
            for arg in args:
                cmd.append(arg)
            for key in kwargs:
                cmd.append('%s=%s' % (key, kwargs[key]))

        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.lvmutils.get_volume_group_info',
            fake_get_volume_group_info))
        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute))

        lvmutils.create_logical_volume('foo', 'bar', 4000, 'fake_helper',
                                       sparse=True)
        self.assertEqual(['lvcreate', '-L', '67108864b', '--virtualsize',
                          '4000b', '-n', 'bar', 'foo', 'attempts=3',
                          'root_helper=fake_helper', 'run_as_root=True'], cmd)

    def test_create_logical_volume_no_space_sparse(self):
        def fake_get_volume_group_info(*args):
            return {'free': 42}

        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.lvmutils.get_volume_group_info',
            fake_get_volume_group_info))

        self.assertRaises(RuntimeError, lvmutils.create_logical_volume,
                          'foo', 'bar', 4000, 'fake_helper', sparse=True)

    def test_list_logical_volumes(self):
        # $ sudo lvs --noheadings -o lv_name raidvg
        # datalv
        # mythlv
        def fake_execute(*args, **kwargs):
            return 'datalv\nmythlv', ''

        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute))

        self.assertEqual(['datalv', 'mythlv'],
                         lvmutils.list_logical_volumes(
                             'foo', 'fake_helper'))

    def test_logical_volume_info(self):
        # $ sudo lvs -o vg_all,lv_all --separator "|" /dev/mapper/raidvg/datalv
        # Fmt|VG UUID|VG|Attr|VSize|VFree|SYS ID|Ext|#Ext|Free|MaxLV|MaxPV|
        #     #PV|#LV|#SN|Seq|VG Tags|#VMda|VMdaFree|VMdaSize|LV UUID|LV|Attr|
        #     Maj|Min|Rahead|KMaj|KMin|KRahead|LSize|#Seg|Origin|OSize|Snap%|
        #     Copy%|Move|Convert|LV Tags|Log|Modules
        # lvm2|px26es-tyyr-KZLF-fwHr-TW6h-0CZy-KrqR1i|raidvg|wz--n-|4.55t|
        #     4.93g||4.00m|1192200|1262|0|0|4|2|0|29||4|91.00k|188.00k|
        #     LznmKH-h7Uo-hSkN-FWvu-3SoT-M8ry-AsgS0U|datalv|-wi-ao|-1|-1|auto|
        #     252|7|128.00k|3.34t|6||0 |||||||
        def fake_execute(*args, **kwargs):
            return (('Fmt|VG UUID|VG|Attr|VSize|VFree|SYS ID|Ext|#Ext|Free|'
                     'MaxLV|MaxPV|#PV|#LV|#SN|Seq|VG Tags|#VMda|VMdaFree|'
                     'VMdaSize|LV UUID|LV|Attr|Maj|Min|Rahead|KMaj|KMin|'
                     'KRahead|LSize|#Seg|Origin|OSize|Snap%|Copy%|Move|'
                     'Convert|LV Tags|Log|Modules\n'
                     'lvm2|px26es-tyyr-KZLF-fwHr-TW6h-0CZy-KrqR1i|raidvg|'
                     'wz--n-|4.55t|4.93g||4.00m|1192200|1262|0|0|4|2|0|29||'
                     '4|91.00k|188.00k|LznmKH-h7Uo-hSkN-FWvu-3SoT-M8ry-AsgS0U|'
                     'datalv|-wi-ao|-1|-1|auto|252|7|128.00k|3.34t|6||0 '
                     '|||||||'), '')

        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute))

        data = lvmutils.logical_volume_info('/dev/mapper/raidvg/datalv',
                                            'fake_helper')
        self.assertEqual('lvm2', data['Fmt'])
        self.assertEqual('px26es-tyyr-KZLF-fwHr-TW6h-0CZy-KrqR1i',
                         data['VG UUID'])
        self.assertEqual('LznmKH-h7Uo-hSkN-FWvu-3SoT-M8ry-AsgS0U',
                         data['LV UUID'])

    def test_logical_volume_info_no_output(self):
        def fake_execute(*args, **kwargs):
            return '', ''

        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute))

        self.assertRaises(RuntimeError, lvmutils.logical_volume_info,
                          '/dev/mapper/raidvg/datalv', 'fake_helper')

    def test_logical_volume_size(self):
        # $ sudo lvs -o lv_size --noheadings --units b --nosuffix
        #    /dev/mapper/raidvg/datalv
        # 3675741224960
        def fake_execute(*args, **kwargs):
            return '3675741224960', ''

        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute))

        self.assertEqual(3675741224960,
                         lvmutils.logical_volume_size(
                             '/dev/mapper/raidvg/datalv', 'fake_helper'))

    def test_clear_logical_volume(self):
        cmds = []

        def fake_logical_volume_size(path, root_helper):
            return 3675741224964

        def fake_execute(*args, **kwargs):
            cmd = []
            for arg in args:
                cmd.append(arg)
            for key in kwargs:
                cmd.append('%s=%s' % (key, kwargs[key]))
            cmds.append(cmd)
            return '', ''

        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.lvmutils.logical_volume_size',
            fake_logical_volume_size))
        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute))

        lvmutils.clear_logical_volume('/dev/mapper/fakevg/fakelv',
                                      'fake_helper')
        self.assertEqual([['dd', 'bs=1048576', 'if=/dev/zero',
                           'of=/dev/mapper/fakevg/fakelv', 'seek=0',
                           'count=3505460', 'oflag=direct', 'run_as_root=True',
                           'root_helper=fake_helper'],
                          ['dd', 'bs=1', 'if=/dev/zero',
                           'of=/dev/mapper/fakevg/fakelv',
                           'seek=3675741224960', 'count=4', 'conv=fdatasync',
                           'run_as_root=True', 'root_helper=fake_helper']],
                         cmds)

    def test_remove_logical_volumes(self):
        cleared = []
        cmds = []

        def fake_clear_logical_volume(path, root_helper):
            cleared.append(path)

        def fake_execute(*args, **kwargs):
            cmd = []
            for arg in args:
                cmd.append(arg)
            for key in kwargs:
                cmd.append('%s=%s' % (key, kwargs[key]))
            cmds.append(cmd)
            return '', ''

        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.lvmutils.clear_logical_volume',
            fake_clear_logical_volume))
        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute))

        lvmutils.remove_logical_volume(['/dev/foo', '/dev/bar'],
                                       'fake_helper')

        self.assertEquals(['/dev/foo', '/dev/bar'], cleared)
        self.assertEquals([['lvremove', '-f', '/dev/foo', '/dev/bar',
                            'run_as_root=True', 'root_helper=fake_helper',
                            'attempts=3']], cmds)
