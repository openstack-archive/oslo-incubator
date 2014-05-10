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


class BaseTestCase(test_base.BaseTestCase):

    def setUp(self, conf=None):
        super(BaseTestCase, self).setUp()
        if conf is None:
            self.conf = cfg.ConfigOpts()
        else:
            self.conf = conf
        self.fconf = cfgfilter.ConfigFilter(
            self.conf,
            cfgfilter.ConfigFilter.THIS_USES_PRIVATE_CFG_IMPL_DETAILS)


class RegisterTestCase(BaseTestCase):

    def test_register_opt_default(self):
        self.fconf.register_opt(cfg.StrOpt('foo', default='bar'))

        self.assertEqual('bar', self.fconf.foo)
        self.assertEqual('bar', self.fconf['foo'])
        self.assertIn('foo', self.fconf)
        self.assertEqual(['foo'], list(self.fconf))
        self.assertEqual(1, len(self.fconf))

        self.assertNotIn('foo', self.conf)
        self.assertEqual(0, len(self.conf))
        self.assertRaises(cfg.NoSuchOptError, getattr, self.conf, 'foo')

    def test_register_opt_none_default(self):
        self.fconf.register_opt(cfg.StrOpt('foo'))

        self.assertIsNone(self.fconf.foo)
        self.assertIsNone(self.fconf['foo'])
        self.assertIn('foo', self.fconf)
        self.assertEqual(['foo'], list(self.fconf))
        self.assertEqual(1, len(self.fconf))

        self.assertNotIn('foo', self.conf)
        self.assertEqual(0, len(self.conf))
        self.assertRaises(cfg.NoSuchOptError, getattr, self.conf, 'foo')

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

        self.assertNotIn('blaa', self.conf)
        self.assertEqual(0, len(self.conf))
        self.assertRaises(cfg.NoSuchOptError, getattr, self.conf, 'blaa')

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

        self.assertNotIn('blaa', self.conf)
        self.assertEqual(0, len(self.conf))
        self.assertRaises(cfg.NoSuchOptError, getattr, self.conf, 'blaa')

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

        self.assertNotIn('blaa', self.conf)
        self.assertEqual(0, len(self.conf))
        self.assertRaises(cfg.NoSuchOptError, getattr, self.conf, 'blaa')

    def test_register_opts(self):
        self.fconf.register_opts([cfg.StrOpt('foo'),
                                  cfg.StrOpt('bar')])
        self.assertIn('foo', self.fconf)
        self.assertIn('bar', self.fconf)
        self.assertNotIn('foo', self.conf)
        self.assertNotIn('bar', self.conf)

    def test_register_cli_opt(self):
        self.fconf.register_cli_opt(cfg.StrOpt('foo'))
        self.assertIn('foo', self.fconf)
        self.assertNotIn('foo', self.conf)

    def test_register_cli_opts(self):
        self.fconf.register_cli_opts([cfg.StrOpt('foo'), cfg.StrOpt('bar')])
        self.assertIn('foo', self.fconf)
        self.assertIn('bar', self.fconf)
        self.assertNotIn('foo', self.conf)
        self.assertNotIn('bar', self.conf)

    def test_register_opts_grouped(self):
        self.fconf.register_opts([cfg.StrOpt('foo'), cfg.StrOpt('bar')],
                                 group='blaa')
        self.assertIn('foo', self.fconf.blaa)
        self.assertIn('bar', self.fconf.blaa)
        self.assertNotIn('blaa', self.conf)

    def test_register_cli_opt_grouped(self):
        self.fconf.register_cli_opt(cfg.StrOpt('foo'), group='blaa')
        self.assertIn('foo', self.fconf.blaa)
        self.assertNotIn('blaa', self.conf)

    def test_register_cli_opts_grouped(self):
        self.fconf.register_cli_opts([cfg.StrOpt('foo'), cfg.StrOpt('bar')],
                                     group='blaa')
        self.assertIn('foo', self.fconf.blaa)
        self.assertIn('bar', self.fconf.blaa)
        self.assertNotIn('blaa', self.conf)

    def test_unknown_opt(self):
        self.assertNotIn('foo', self.fconf)
        self.assertEqual(0, len(self.fconf))
        self.assertRaises(cfg.NoSuchOptError, getattr, self.fconf, 'foo')
        self.assertNotIn('blaa', self.conf)

    def test_blocked_opt(self):
        self.conf.register_opt(cfg.StrOpt('foo'))

        self.assertIn('foo', self.conf)
        self.assertEqual(1, len(self.conf))
        self.assertIsNone(self.conf.foo)
        self.assertNotIn('foo', self.fconf)
        self.assertEqual(0, len(self.fconf))
        self.assertRaises(cfg.NoSuchOptError, getattr, self.fconf, 'foo')


class ImportTestCase(BaseTestCase):

    def setUp(self):
        super(ImportTestCase, self).setUp(cfg.CONF)

    def test_import_opt(self):
        self.assertFalse(hasattr(self.conf, 'blaa'))
        self.conf.import_opt('blaa', 'tests.testmods.blaa_opt')
        self.assertTrue(hasattr(self.conf, 'blaa'))
        self.assertFalse(hasattr(self.fconf, 'blaa'))
        self.fconf.import_opt('blaa', 'tests.testmods.blaa_opt')
        self.assertTrue(hasattr(self.fconf, 'blaa'))

    def test_import_opt_in_group(self):
        self.assertFalse(hasattr(self.conf, 'bar'))
        self.conf.import_opt('foo', 'tests.testmods.bar_foo_opt', group='bar')
        self.assertTrue(hasattr(self.conf, 'bar'))
        self.assertTrue(hasattr(self.conf.bar, 'foo'))
        self.assertFalse(hasattr(self.fconf, 'bar'))
        self.fconf.import_opt('foo', 'tests.testmods.bar_foo_opt', group='bar')
        self.assertTrue(hasattr(self.fconf, 'bar'))
        self.assertTrue(hasattr(self.fconf.bar, 'foo'))

    def test_import_group(self):
        self.assertFalse(hasattr(self.conf, 'baar'))
        self.conf.import_group('baar', 'tests.testmods.baar_baa_opt')
        self.assertTrue(hasattr(self.conf, 'baar'))
        self.assertTrue(hasattr(self.conf.baar, 'baa'))
        self.assertFalse(hasattr(self.fconf, 'baar'))
        self.fconf.import_group('baar', 'tests.testmods.baar_baa_opt')
        self.assertTrue(hasattr(self.fconf, 'baar'))
        self.assertTrue(hasattr(self.fconf.baar, 'baa'))
