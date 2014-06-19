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
from oslotest import base as test_base

from openstack.common import cfgfilter


class ConfigFilterTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(ConfigFilterTestCase, self).setUp()
        self.conf = cfg.ConfigOpts()
        self.fconf = cfgfilter.ConfigFilter(self.conf)

    def test_register_opt_default(self):
        self.fconf.register_opt(cfg.StrOpt('foo', default='bar'))

        self.assertEqual('bar', self.fconf.foo)
        self.assertEqual('bar', self.fconf['foo'])
        self.assertIn('foo', self.fconf)
        self.assertEqual(['foo'], list(self.fconf))
        self.assertEqual(1, len(self.fconf))

    def test_register_opt_none_default(self):
        self.fconf.register_opt(cfg.StrOpt('foo'))

        self.assertIsNone(self.fconf.foo)
        self.assertIsNone(self.fconf['foo'])
        self.assertIn('foo', self.fconf)
        self.assertEqual(['foo'], list(self.fconf))
        self.assertEqual(1, len(self.fconf))

    def test_register_grouped_opt_default(self):
        self.fconf.register_opt(cfg.StrOpt('foo', default='bar'),
                                group='blaa')

        self.assertEqual('bar', self.fconf.blaa.foo)
        self.assertEqual('bar', self.fconf['blaa']['foo'])
        self.assertIn('blaa', self.fconf)
        self.assertIn('foo', self.fconf.blaa)
        self.assertEqual(['blaa'], list(self.fconf))
        self.assertEqual(['foo'], list(self.fconf.blaa))
        self.assertEqual(1, len(self.fconf))
        self.assertEqual(1, len(self.fconf.blaa))

    def test_register_grouped_opt_none_default(self):
        self.fconf.register_opt(cfg.StrOpt('foo'), group='blaa')

        self.assertIsNone(self.fconf.blaa.foo)
        self.assertIsNone(self.fconf['blaa']['foo'])
        self.assertIn('blaa', self.fconf)
        self.assertIn('foo', self.fconf.blaa)
        self.assertEqual(['blaa'], list(self.fconf))
        self.assertEqual(['foo'], list(self.fconf.blaa))
        self.assertEqual(1, len(self.fconf))
        self.assertEqual(1, len(self.fconf.blaa))

    def test_register_group(self):
        group = cfg.OptGroup('blaa')
        self.fconf.register_group(group)
        self.fconf.register_opt(cfg.StrOpt('foo'), group=group)

        self.assertIsNone(self.fconf.blaa.foo)
        self.assertIsNone(self.fconf['blaa']['foo'])
        self.assertIn('blaa', self.fconf)
        self.assertIn('foo', self.fconf.blaa)
        self.assertEqual(['blaa'], list(self.fconf))
        self.assertEqual(['foo'], list(self.fconf.blaa))
        self.assertEqual(1, len(self.fconf))
        self.assertEqual(1, len(self.fconf.blaa))

    def test_register_opts(self):
        self.fconf.register_opts([cfg.StrOpt('foo'),
                                  cfg.StrOpt('bar')])
        self.assertIn('foo', self.fconf)
        self.assertIn('bar', self.fconf)

    def test_register_cli_opt(self):
        self.fconf.register_cli_opt(cfg.StrOpt('foo'))
        self.assertIn('foo', self.fconf)

    def test_register_cli_opts(self):
        self.fconf.register_cli_opts([cfg.StrOpt('foo'), cfg.StrOpt('bar')])
        self.assertIn('foo', self.fconf)
        self.assertIn('bar', self.fconf)

    def test_register_opts_grouped(self):
        self.fconf.register_opts([cfg.StrOpt('foo'), cfg.StrOpt('bar')],
                                 group='blaa')
        self.assertIn('foo', self.fconf.blaa)
        self.assertIn('bar', self.fconf.blaa)

    def test_register_cli_opt_grouped(self):
        self.fconf.register_cli_opt(cfg.StrOpt('foo'), group='blaa')
        self.assertIn('foo', self.fconf.blaa)

    def test_register_cli_opts_grouped(self):
        self.fconf.register_cli_opts([cfg.StrOpt('foo'), cfg.StrOpt('bar')],
                                     group='blaa')
        self.assertIn('foo', self.fconf.blaa)
        self.assertIn('bar', self.fconf.blaa)

    def test_unknown_opt(self):
        self.assertNotIn('foo', self.fconf)
        self.assertEqual(0, len(self.fconf))
        self.assertRaises(cfg.NoSuchOptError, getattr, self.fconf, 'foo')

    def test_blocked_opt(self):
        self.conf.register_opt(cfg.StrOpt('foo'))

        self.assertIn('foo', self.conf)
        self.assertEqual(1, len(self.conf))
        self.assertIsNone(self.conf.foo)
        self.assertNotIn('foo', self.fconf)
        self.assertEqual(0, len(self.fconf))
        self.assertRaises(cfg.NoSuchOptError, getattr, self.fconf, 'foo')

    def test_import_opt(self):
        self.fconf = cfgfilter.ConfigFilter(cfg.CONF)
        self.assertFalse(hasattr(self.fconf, 'fblaa'))
        self.fconf.import_opt('fblaa', 'tests.testmods.fblaa_opt')
        self.assertTrue(hasattr(self.fconf, 'fblaa'))

    def test_import_opt_in_group(self):
        self.fconf = cfgfilter.ConfigFilter(cfg.CONF)
        self.assertFalse(hasattr(self.fconf, 'fbar'))
        self.fconf.import_opt('foo', 'tests.testmods.fbar_foo_opt',
                              group='fbar')
        self.assertTrue(hasattr(self.fconf, 'fbar'))
        self.assertTrue(hasattr(self.fconf.fbar, 'foo'))

    def test_import_group(self):
        self.fconf = cfgfilter.ConfigFilter(cfg.CONF)
        self.assertFalse(hasattr(self.fconf, 'fbaar'))
        self.fconf.import_group('fbaar', 'tests.testmods.fbaar_baa_opt')
        self.assertTrue(hasattr(self.fconf, 'fbaar'))
        self.assertTrue(hasattr(self.fconf.fbaar, 'baa'))
