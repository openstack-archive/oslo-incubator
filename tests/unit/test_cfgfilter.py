# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 Red Hat, Inc.
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

from oslo.config import cfg

from openstack.common import cfgfilter
from tests import utils


class ConfigFilterTestCase(utils.BaseTestCase):

    def setUp(self):
        super(ConfigFilterTestCase, self).setUp()
        self.conf = cfg.ConfigOpts()
        self.fconf = cfgfilter.ConfigFilter(self.conf)

    def test_register_opt_default(self):
        self.fconf.register_opt(cfg.StrOpt('foo', default='bar'))

        self.assertEquals(self.fconf.foo, 'bar')
        self.assertEquals(self.fconf['foo'], 'bar')
        self.assertTrue('foo' in self.fconf)
        self.assertEquals(list(self.fconf), ['foo'])
        self.assertEquals(len(self.fconf), 1)

    def test_register_opt_none_default(self):
        self.fconf.register_opt(cfg.StrOpt('foo'))

        self.assertTrue(self.fconf.foo is None)
        self.assertTrue(self.fconf['foo'] is None)
        self.assertTrue('foo' in self.fconf)
        self.assertEquals(list(self.fconf), ['foo'])
        self.assertEquals(len(self.fconf), 1)

    def test_register_grouped_opt_default(self):
        self.fconf.register_opt(cfg.StrOpt('foo', default='bar'),
                                group='blaa')

        self.assertEquals(self.fconf.blaa.foo, 'bar')
        self.assertEquals(self.fconf['blaa']['foo'], 'bar')
        self.assertTrue('blaa' in self.fconf)
        self.assertTrue('foo' in self.fconf.blaa)
        self.assertEquals(list(self.fconf), ['blaa'])
        self.assertEquals(list(self.fconf.blaa), ['foo'])
        self.assertEquals(len(self.fconf), 1)
        self.assertEquals(len(self.fconf.blaa), 1)

    def test_register_grouped_opt_none_default(self):
        self.fconf.register_opt(cfg.StrOpt('foo'), group='blaa')

        self.assertTrue(self.fconf.blaa.foo is None)
        self.assertTrue(self.fconf['blaa']['foo'] is None)
        self.assertTrue('blaa' in self.fconf)
        self.assertTrue('foo' in self.fconf.blaa)
        self.assertEquals(list(self.fconf), ['blaa'])
        self.assertEquals(list(self.fconf.blaa), ['foo'])
        self.assertEquals(len(self.fconf), 1)
        self.assertEquals(len(self.fconf.blaa), 1)

    def test_register_group(self):
        group = cfg.OptGroup('blaa')
        self.fconf.register_group(group)
        self.fconf.register_opt(cfg.StrOpt('foo'), group=group)

        self.assertTrue(self.fconf.blaa.foo is None)
        self.assertTrue(self.fconf['blaa']['foo'] is None)
        self.assertTrue('blaa' in self.fconf)
        self.assertTrue('foo' in self.fconf.blaa)
        self.assertEquals(list(self.fconf), ['blaa'])
        self.assertEquals(list(self.fconf.blaa), ['foo'])
        self.assertEquals(len(self.fconf), 1)
        self.assertEquals(len(self.fconf.blaa), 1)

    def test_unknown_opt(self):
        self.assertFalse('foo' in self.fconf)
        self.assertEquals(len(self.fconf), 0)
        self.assertRaises(cfg.NoSuchOptError, getattr, self.fconf, 'foo')

    def test_blocked_opt(self):
        self.conf.register_opt(cfg.StrOpt('foo'))

        self.assertTrue('foo' in self.conf)
        self.assertEquals(len(self.conf), 1)
        self.assertTrue(self.conf.foo is None)
        self.assertFalse('foo' in self.fconf)
        self.assertEquals(len(self.fconf), 0)
        self.assertRaises(cfg.NoSuchOptError, getattr, self.fconf, 'foo')

    def test_import_opt(self):
        self.fconf = cfgfilter.ConfigFilter(cfg.CONF)
        self.assertFalse(hasattr(self.fconf, 'blaa'))
        self.fconf.import_opt('blaa', 'tests.testmods.blaa_opt')
        self.assertTrue(hasattr(self.fconf, 'blaa'))

    def test_import_opt_in_group(self):
        self.fconf = cfgfilter.ConfigFilter(cfg.CONF)
        self.assertFalse(hasattr(self.fconf, 'bar'))
        self.fconf.import_opt('foo', 'tests.testmods.bar_foo_opt', group='bar')
        self.assertTrue(hasattr(self.fconf, 'bar'))
        self.assertTrue(hasattr(self.fconf.bar, 'foo'))

    def test_import_group(self):
        self.fconf = cfgfilter.ConfigFilter(cfg.CONF)
        self.assertFalse(hasattr(self.fconf, 'baar'))
        self.fconf.import_group('baar', 'tests.testmods.baar_baa_opt')
        self.assertTrue(hasattr(self.fconf, 'baar'))
        self.assertTrue(hasattr(self.fconf.baar, 'baa'))
