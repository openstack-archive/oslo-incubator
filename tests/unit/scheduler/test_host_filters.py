# Copyright 2011 OpenStack Foundation.
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
Tests For Scheduler Host Filters.
"""

from openstack.common import context
from openstack.common import jsonutils
from openstack.common.scheduler import filters
from openstack.common.scheduler.filters import extra_specs_ops
from openstack.common import test
from tests.unit.scheduler import fake_hosts as fakes


class TestFilter(filters.BaseHostFilter):
    pass


class TestBogusFilter(object):
    """Class that doesn't inherit from BaseHostFilter"""
    pass


class ExtraSpecsOpsTestCase(test.BaseTestCase):
    def _do_extra_specs_ops_test(self, value, req, matches):
        assertion = self.assertTrue if matches else self.assertFalse
        assertion(extra_specs_ops.match(value, req))

    def test_extra_specs_matches_simple(self):
        self._do_extra_specs_ops_test(
            value='1',
            req='1',
            matches=True)

    def test_extra_specs_fails_simple(self):
        self._do_extra_specs_ops_test(
            value='',
            req='1',
            matches=False)

    def test_extra_specs_fails_simple2(self):
        self._do_extra_specs_ops_test(
            value='3',
            req='1',
            matches=False)

    def test_extra_specs_fails_simple3(self):
        self._do_extra_specs_ops_test(
            value='222',
            req='2',
            matches=False)

    def test_extra_specs_fails_with_bogus_ops(self):
        self._do_extra_specs_ops_test(
            value='4',
            req='> 2',
            matches=False)

    def test_extra_specs_matches_with_op_eq(self):
        self._do_extra_specs_ops_test(
            value='123',
            req='= 123',
            matches=True)

    def test_extra_specs_matches_with_op_eq2(self):
        self._do_extra_specs_ops_test(
            value='124',
            req='= 123',
            matches=True)

    def test_extra_specs_fails_with_op_eq(self):
        self._do_extra_specs_ops_test(
            value='34',
            req='= 234',
            matches=False)

    def test_extra_specs_fails_with_op_eq3(self):
        self._do_extra_specs_ops_test(
            value='34',
            req='=',
            matches=False)

    def test_extra_specs_matches_with_op_seq(self):
        self._do_extra_specs_ops_test(
            value='123',
            req='s== 123',
            matches=True)

    def test_extra_specs_fails_with_op_seq(self):
        self._do_extra_specs_ops_test(
            value='1234',
            req='s== 123',
            matches=False)

    def test_extra_specs_matches_with_op_sneq(self):
        self._do_extra_specs_ops_test(
            value='1234',
            req='s!= 123',
            matches=True)

    def test_extra_specs_fails_with_op_sneq(self):
        self._do_extra_specs_ops_test(
            value='123',
            req='s!= 123',
            matches=False)

    def test_extra_specs_fails_with_op_sge(self):
        self._do_extra_specs_ops_test(
            value='1000',
            req='s>= 234',
            matches=False)

    def test_extra_specs_fails_with_op_sle(self):
        self._do_extra_specs_ops_test(
            value='1234',
            req='s<= 1000',
            matches=False)

    def test_extra_specs_fails_with_op_sl(self):
        self._do_extra_specs_ops_test(
            value='2',
            req='s< 12',
            matches=False)

    def test_extra_specs_fails_with_op_sg(self):
        self._do_extra_specs_ops_test(
            value='12',
            req='s> 2',
            matches=False)

    def test_extra_specs_matches_with_op_in(self):
        self._do_extra_specs_ops_test(
            value='12311321',
            req='<in> 11',
            matches=True)

    def test_extra_specs_matches_with_op_in2(self):
        self._do_extra_specs_ops_test(
            value='12311321',
            req='<in> 12311321',
            matches=True)

    def test_extra_specs_matches_with_op_in3(self):
        self._do_extra_specs_ops_test(
            value='12311321',
            req='<in> 12311321 <in>',
            matches=True)

    def test_extra_specs_fails_with_op_in(self):
        self._do_extra_specs_ops_test(
            value='12310321',
            req='<in> 11',
            matches=False)

    def test_extra_specs_fails_with_op_in2(self):
        self._do_extra_specs_ops_test(
            value='12310321',
            req='<in> 11 <in>',
            matches=False)

    def test_extra_specs_matches_with_op_is(self):
        self._do_extra_specs_ops_test(
            value=True,
            req='<is> True',
            matches=True)

    def test_extra_specs_matches_with_op_is2(self):
        self._do_extra_specs_ops_test(
            value=False,
            req='<is> False',
            matches=True)

    def test_extra_specs_matches_with_op_is3(self):
        self._do_extra_specs_ops_test(
            value=False,
            req='<is> Nonsense',
            matches=True)

    def test_extra_specs_fails_with_op_is(self):
        self._do_extra_specs_ops_test(
            value=True,
            req='<is> False',
            matches=False)

    def test_extra_specs_fails_with_op_is2(self):
        self._do_extra_specs_ops_test(
            value=False,
            req='<is> True',
            matches=False)

    def test_extra_specs_matches_with_op_or(self):
        self._do_extra_specs_ops_test(
            value='12',
            req='<or> 11 <or> 12',
            matches=True)

    def test_extra_specs_matches_with_op_or2(self):
        self._do_extra_specs_ops_test(
            value='12',
            req='<or> 11 <or> 12 <or>',
            matches=True)

    def test_extra_specs_fails_with_op_or(self):
        self._do_extra_specs_ops_test(
            value='13',
            req='<or> 11 <or> 12',
            matches=False)

    def test_extra_specs_fails_with_op_or2(self):
        self._do_extra_specs_ops_test(
            value='13',
            req='<or> 11 <or> 12 <or>',
            matches=False)

    def test_extra_specs_matches_with_op_le(self):
        self._do_extra_specs_ops_test(
            value='2',
            req='<= 10',
            matches=True)

    def test_extra_specs_fails_with_op_le(self):
        self._do_extra_specs_ops_test(
            value='3',
            req='<= 2',
            matches=False)

    def test_extra_specs_matches_with_op_ge(self):
        self._do_extra_specs_ops_test(
            value='3',
            req='>= 1',
            matches=True)

    def test_extra_specs_fails_with_op_ge(self):
        self._do_extra_specs_ops_test(
            value='2',
            req='>= 3',
            matches=False)


class HostFiltersTestCase(test.BaseTestCase):
    """Test case for host filters."""

    def setUp(self):
        super(HostFiltersTestCase, self).setUp()
        self.context = context.RequestContext('fake', 'fake')
        self.json_query = jsonutils.dumps(
            ['and', ['>=', '$free_ram_mb', 1024],
             ['>=', '$free_disk_mb', 200 * 1024]])
        namespace = 'openstack.common.scheduler.filters'
        filter_handler = filters.HostFilterHandler(namespace)
        classes = filter_handler.get_all_classes()
        self.class_map = {}
        for cls in classes:
            self.class_map[cls.__name__] = cls

    def test_all_filters(self):
        # Double check at least a couple of known filters exist
        self.assertTrue('JsonFilter' in self.class_map)
        self.assertTrue('CapabilitiesFilter' in self.class_map)

    def _do_test_type_filter_extra_specs(self, ecaps, especs, passes):
        filt_cls = self.class_map['CapabilitiesFilter']()
        capabilities = {'enabled': True}
        capabilities.update(ecaps)
        service = {'disabled': False}
        filter_properties = {'resource_type': {'name': 'fake_type',
                                               'extra_specs': especs}}
        host = fakes.FakeHostState('host1',
                                   {'free_capacity_gb': 1024,
                                    'capabilities': capabilities,
                                    'service': service})
        assertion = self.assertTrue if passes else self.assertFalse
        assertion(filt_cls.host_passes(host, filter_properties))

    def test_capability_filter_passes_extra_specs_simple(self):
        self._do_test_type_filter_extra_specs(
            ecaps={'opt1': '1', 'opt2': '2'},
            especs={'opt1': '1', 'opt2': '2'},
            passes=True)

    def test_capability_filter_fails_extra_specs_simple(self):
        self._do_test_type_filter_extra_specs(
            ecaps={'opt1': '1', 'opt2': '2'},
            especs={'opt1': '1', 'opt2': '222'},
            passes=False)

    def test_capability_filter_passes_extra_specs_complex(self):
        self._do_test_type_filter_extra_specs(
            ecaps={'opt1': 10, 'opt2': 5},
            especs={'opt1': '>= 2', 'opt2': '<= 8'},
            passes=True)

    def test_capability_filter_fails_extra_specs_complex(self):
        self._do_test_type_filter_extra_specs(
            ecaps={'opt1': 10, 'opt2': 5},
            especs={'opt1': '>= 2', 'opt2': '>= 8'},
            passes=False)

    def test_capability_filter_passes_scope_extra_specs(self):
        self._do_test_type_filter_extra_specs(
            ecaps={'scope_lv1': {'opt1': 10}},
            especs={'capabilities:scope_lv1:opt1': '>= 2'},
            passes=True)

    def test_capability_filter_passes_fakescope_extra_specs(self):
        self._do_test_type_filter_extra_specs(
            ecaps={'scope_lv1': {'opt1': 10}, 'opt2': 5},
            especs={'scope_lv1:opt1': '= 2', 'opt2': '>= 3'},
            passes=True)

    def test_capability_filter_fails_scope_extra_specs(self):
        self._do_test_type_filter_extra_specs(
            ecaps={'scope_lv1': {'opt1': 10}},
            especs={'capabilities:scope_lv1:opt1': '<= 2'},
            passes=False)

    def test_capability_filter_passes_multi_level_scope_extra_specs(self):
        self._do_test_type_filter_extra_specs(
            ecaps={'scope_lv0': {'scope_lv1':
                                 {'scope_lv2': {'opt1': 10}}}},
            especs={'capabilities:scope_lv0:scope_lv1:scope_lv2:opt1': '>= 2'},
            passes=True)

    def test_capability_filter_fails_wrong_scope_extra_specs(self):
        self._do_test_type_filter_extra_specs(
            ecaps={'scope_lv0': {'opt1': 10}},
            especs={'capabilities:scope_lv1:opt1': '>= 2'},
            passes=False)

    def test_json_filter_passes(self):
        filt_cls = self.class_map['JsonFilter']()
        filter_properties = {'resource_type': {'memory_mb': 1024,
                                               'root_gb': 200,
                                               'ephemeral_gb': 0},
                             'scheduler_hints': {'query': self.json_query}}
        capabilities = {'enabled': True}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 1024,
                                    'free_disk_mb': 200 * 1024,
                                    'capabilities': capabilities})
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

    def test_json_filter_passes_with_no_query(self):
        filt_cls = self.class_map['JsonFilter']()
        filter_properties = {'resource_type': {'memory_mb': 1024,
                                               'root_gb': 200,
                                               'ephemeral_gb': 0}}
        capabilities = {'enabled': True}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 0,
                                    'free_disk_mb': 0,
                                    'capabilities': capabilities})
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

    def test_json_filter_fails_on_memory(self):
        filt_cls = self.class_map['JsonFilter']()
        filter_properties = {'resource_type': {'memory_mb': 1024,
                                               'root_gb': 200,
                                               'ephemeral_gb': 0},
                             'scheduler_hints': {'query': self.json_query}}
        capabilities = {'enabled': True}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 1023,
                                    'free_disk_mb': 200 * 1024,
                                    'capabilities': capabilities})
        self.assertFalse(filt_cls.host_passes(host, filter_properties))

    def test_json_filter_fails_on_disk(self):
        filt_cls = self.class_map['JsonFilter']()
        filter_properties = {'resource_type': {'memory_mb': 1024,
                                               'root_gb': 200,
                                               'ephemeral_gb': 0},
                             'scheduler_hints': {'query': self.json_query}}
        capabilities = {'enabled': True}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 1024,
                                    'free_disk_mb': (200 * 1024) - 1,
                                    'capabilities': capabilities})
        self.assertFalse(filt_cls.host_passes(host, filter_properties))

    def test_json_filter_fails_on_caps_disabled(self):
        filt_cls = self.class_map['JsonFilter']()
        json_query = jsonutils.dumps(
            ['and', ['>=', '$free_ram_mb', 1024],
             ['>=', '$free_disk_mb', 200 * 1024],
             '$capabilities.enabled'])
        filter_properties = {'resource_type': {'memory_mb': 1024,
                                               'root_gb': 200,
                                               'ephemeral_gb': 0},
                             'scheduler_hints': {'query': json_query}}
        capabilities = {'enabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 1024,
                                    'free_disk_mb': 200 * 1024,
                                    'capabilities': capabilities})
        self.assertFalse(filt_cls.host_passes(host, filter_properties))

    def test_json_filter_fails_on_service_disabled(self):
        filt_cls = self.class_map['JsonFilter']()
        json_query = jsonutils.dumps(
            ['and', ['>=', '$free_ram_mb', 1024],
             ['>=', '$free_disk_mb', 200 * 1024],
             ['not', '$service.disabled']])
        filter_properties = {'resource_type': {'memory_mb': 1024,
                                               'local_gb': 200},
                             'scheduler_hints': {'query': json_query}}
        capabilities = {'enabled': True}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 1024,
                                    'free_disk_mb': 200 * 1024,
                                    'capabilities': capabilities})
        self.assertFalse(filt_cls.host_passes(host, filter_properties))

    def test_json_filter_happy_day(self):
        """Test json filter more thoroughly."""
        filt_cls = self.class_map['JsonFilter']()
        raw = ['and',
               '$capabilities.enabled',
               ['=', '$capabilities.opt1', 'match'],
               ['or',
                ['and',
                 ['<', '$free_ram_mb', 30],
                 ['<', '$free_disk_mb', 300]],
                ['and',
                 ['>', '$free_ram_mb', 30],
                 ['>', '$free_disk_mb', 300]]]]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }

        # Passes
        capabilities = {'enabled': True, 'opt1': 'match'}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 10,
                                    'free_disk_mb': 200,
                                    'capabilities': capabilities,
                                    'service': service})
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

        # Passes
        capabilities = {'enabled': True, 'opt1': 'match'}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 40,
                                    'free_disk_mb': 400,
                                    'capabilities': capabilities,
                                    'service': service})
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

        # Fails due to capabilities being disabled
        capabilities = {'enabled': False, 'opt1': 'match'}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 40,
                                    'free_disk_mb': 400,
                                    'capabilities': capabilities,
                                    'service': service})
        self.assertFalse(filt_cls.host_passes(host, filter_properties))

        # Fails due to being exact memory/disk we don't want
        capabilities = {'enabled': True, 'opt1': 'match'}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 30,
                                    'free_disk_mb': 300,
                                    'capabilities': capabilities,
                                    'service': service})
        self.assertFalse(filt_cls.host_passes(host, filter_properties))

        # Fails due to memory lower but disk higher
        capabilities = {'enabled': True, 'opt1': 'match'}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 20,
                                    'free_disk_mb': 400,
                                    'capabilities': capabilities,
                                    'service': service})
        self.assertFalse(filt_cls.host_passes(host, filter_properties))

        # Fails due to capabilities 'opt1' not equal
        capabilities = {'enabled': True, 'opt1': 'no-match'}
        service = {'enabled': True}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 20,
                                    'free_disk_mb': 400,
                                    'capabilities': capabilities,
                                    'service': service})
        self.assertFalse(filt_cls.host_passes(host, filter_properties))

    def test_json_filter_basic_operators(self):
        filt_cls = self.class_map['JsonFilter']()
        host = fakes.FakeHostState('host1',
                                   {'capabilities': {'enabled': True}})
        # (operator, arguments, expected_result)
        ops_to_test = [
            ['=', [1, 1], True],
            ['=', [1, 2], False],
            ['<', [1, 2], True],
            ['<', [1, 1], False],
            ['<', [2, 1], False],
            ['>', [2, 1], True],
            ['>', [2, 2], False],
            ['>', [2, 3], False],
            ['<=', [1, 2], True],
            ['<=', [1, 1], True],
            ['<=', [2, 1], False],
            ['>=', [2, 1], True],
            ['>=', [2, 2], True],
            ['>=', [2, 3], False],
            ['in', [1, 1], True],
            ['in', [1, 1, 2, 3], True],
            ['in', [4, 1, 2, 3], False],
            ['not', [True], False],
            ['not', [False], True],
            ['or', [True, False], True],
            ['or', [False, False], False],
            ['and', [True, True], True],
            ['and', [False, False], False],
            ['and', [True, False], False],
            # Nested ((True or False) and (2 > 1)) == Passes
            ['and', [['or', True, False], ['>', 2, 1]], True]]

        for (op, args, expected) in ops_to_test:
            raw = [op] + args
            filter_properties = {
                'scheduler_hints': {
                    'query': jsonutils.dumps(raw),
                },
            }
            self.assertEqual(expected,
                             filt_cls.host_passes(host, filter_properties))

        # This results in [False, True, False, True] and if any are True
        # then it passes...
        raw = ['not', True, False, True, False]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

        # This results in [False, False, False] and if any are True
        # then it passes...which this doesn't
        raw = ['not', True, True, True]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertFalse(filt_cls.host_passes(host, filter_properties))

    def test_json_filter_unknown_operator_raises(self):
        filt_cls = self.class_map['JsonFilter']()
        raw = ['!=', 1, 2]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        host = fakes.FakeHostState('host1',
                                   {'capabilities': {'enabled': True}})
        self.assertRaises(KeyError,
                          filt_cls.host_passes, host, filter_properties)

    def test_json_filter_empty_filters_pass(self):
        filt_cls = self.class_map['JsonFilter']()
        host = fakes.FakeHostState('host1',
                                   {'capabilities': {'enabled': True}})

        raw = []
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertTrue(filt_cls.host_passes(host, filter_properties))
        raw = {}
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

    def test_json_filter_invalid_num_arguments_fails(self):
        filt_cls = self.class_map['JsonFilter']()
        host = fakes.FakeHostState('host1',
                                   {'capabilities': {'enabled': True}})

        raw = ['>', ['and', ['or', ['not', ['<', ['>=', ['<=', ['in', ]]]]]]]]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertFalse(filt_cls.host_passes(host, filter_properties))

        raw = ['>', 1]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertFalse(filt_cls.host_passes(host, filter_properties))

    def test_json_filter_unknown_variable_ignored(self):
        filt_cls = self.class_map['JsonFilter']()
        host = fakes.FakeHostState('host1',
                                   {'capabilities': {'enabled': True}})

        raw = ['=', '$........', 1, 1]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

        raw = ['=', '$foo', 2, 2]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertTrue(filt_cls.host_passes(host, filter_properties))
