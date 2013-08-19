# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010-2011 OpenStack Foundation
# Copyright 2012-2013 IBM Corp.
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
import itertools
import testtools.matchers

import alembic
import mock
import sqlalchemy

from openstack.common.db.sqlalchemy import test_migrations as migrate
from openstack.common import log as logging

from tests.unit.db.sqlalchemy import fake
from tests import utils as test_utils

LOG = logging.getLogger(__name__)
MismatchError = testtools.matchers.MismatchError


class TestWalkVersions(test_utils.BaseTestCase, migrate.WalkVersionsMixin):
    def setUp(self):
        super(TestWalkVersions, self).setUp()
        self.migration_api = mock.MagicMock()
        self.engine = mock.MagicMock()
        self.REPOSITORY = mock.MagicMock()
        self.INIT_VERSION = 4
        self.alembic_version = None
        self.alembic_config = mock.MagicMock()

        self.mock_upgrade = mock.patch('alembic.command.upgrade')
        self.mock_downgrade = mock.patch('alembic.command.downgrade')
        self.mock_rev = mock.patch('alembic.migration.MigrationContext.'
                                   'configure')
        self.vers = ['1', '2', '3']
        self.down_vers = ['-1', '1', '2']

    def test_migrate_up_alembic(self):
        self.mock_upgrade.start()
        env = self.mock_rev.start()
        env.return_value.get_current_revision.return_value = 141
        self._migrate_up(self.engine, 141, alembic=True)
        alembic.command.upgrade.assert_called_with(self.alembic_config, 141)
        self.mock_upgrade.stop()
        self.mock_rev.stop()

    def test_migrate_up_alembic_failed(self):
        self.mock_upgrade.start()
        env = self.mock_rev.start()
        env.return_value.get_current_revision.return_value = 1
        self.assertRaises(MismatchError, self._migrate_up, self.engine,
                          141, alembic=True)
        alembic.command.upgrade.assert_called_with(self.alembic_config, 141)
        self.mock_upgrade.stop()
        self.mock_rev.stop()

    def test_migrate_up_alembic_with_data(self):
        self.mock_upgrade.start()
        env = self.mock_rev.start()
        env.return_value.get_current_revision.return_value = 141
        test_value = {"a": 1, "b": 2}
        self._pre_upgrade_141 = mock.MagicMock()
        self._pre_upgrade_141.return_value = test_value
        self._check_141 = mock.MagicMock()

        self._migrate_up(self.engine, 141, with_data=True, alembic=True)

        self._pre_upgrade_141.assert_called_with(self.engine)
        self._check_141.assert_called_with(self.engine, test_value)
        alembic.command.upgrade.assert_called_with(self.alembic_config, 141)
        self.mock_upgrade.stop()
        self.mock_rev.stop()

    def test_migrate_down_alembic(self):
        self.mock_downgrade.start()
        env = self.mock_rev.start()
        env.return_value.get_current_revision.return_value = 141
        self._migrate_down(self.engine, 141, alembic=True)
        alembic.command.downgrade.assert_called_with(self.alembic_config, 141)
        self.mock_downgrade.stop()
        self.mock_rev.stop()

    def test_migrate_down_alembic_failed(self):
        self.mock_downgrade.start()
        env = self.mock_rev.start()
        env.return_value.get_current_revision.return_value = 1
        self.assertRaises(MismatchError, self._migrate_down, self.engine,
                          141, alembic=True)
        alembic.command.downgrade.assert_called_with(self.alembic_config, 141)
        self.mock_downgrade.stop()
        self.mock_rev.stop()

    def test_migrate_down_alembic_with_data(self):
        self.mock_downgrade.start()
        env = self.mock_rev.start()
        env.return_value.get_current_revision.return_value = 141
        self._post_downgrade_123 = mock.MagicMock()

        self._migrate_down(self.engine, 141, with_data=True, alembic=True,
                           next_version='123')

        self._post_downgrade_123.assert_called_with(self.engine)
        alembic.command.downgrade.assert_called_with(self.alembic_config, 141)
        self.mock_downgrade.stop()
        self.mock_rev.stop()

    def test_migrate_up(self):
        self.migration_api.db_version.return_value = 141

        self._migrate_up(self.engine, 141)

        self.migration_api.upgrade.assert_called_with(
            self.engine, self.REPOSITORY, 141)
        self.migration_api.db_version.assert_called_with(
            self.engine, self.REPOSITORY)

    def test_migrate_up_with_data(self):
        test_value = {"a": 1, "b": 2}
        self.migration_api.db_version.return_value = 141
        self._pre_upgrade_141 = mock.MagicMock()
        self._pre_upgrade_141.return_value = test_value
        self._check_141 = mock.MagicMock()

        self._migrate_up(self.engine, 141, True)

        self._pre_upgrade_141.assert_called_with(self.engine)
        self._check_141.assert_called_with(self.engine, test_value)

    def test_migrate_down(self):
        self.migration_api.db_version.return_value = 42

        self.assertTrue(self._migrate_down(self.engine, 42))
        self.migration_api.db_version.assert_called_with(
            self.engine, self.REPOSITORY)

    def test_migrate_down_not_implemented(self):
        self.migration_api.downgrade.side_effect = NotImplementedError
        self.assertFalse(self._migrate_down(self.engine, 42))

    def test_migrate_down_with_data(self):
        self._post_downgrade_043 = mock.MagicMock()
        self.migration_api.db_version.return_value = 42

        self._migrate_down(self.engine, 42, True)

        self._post_downgrade_043.assert_called_with(self.engine)

    @mock.patch.object(migrate.WalkVersionsMixin, '_get_alembic_versions',
                       return_value=['1', '2', '3'])
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def _test_walk_versions_alembic(self, upgraded, downgraded, snake,
                                    downgrade, versions, _migrate_up,
                                    _migrate_down):
        self.engine.url = 'fake_url'
        self._walk_versions_alembic(self.engine, snake, downgrade)
        self.assertEqual(self._migrate_up.call_args_list, upgraded)
        self.assertEqual(self._migrate_down.call_args_list, downgraded)

    def test_walk_versions_alembic_default(self):
        upgraded = [mock.call(self.engine, v, with_data=True, alembic=True)
                    for v in self.vers]
        downgraded = [mock.call(self.engine, self.down_vers[v], alembic=True,
                                next_version=self.vers[v])
                      for v in reversed(range(3))]
        self._test_walk_versions_alembic(upgraded, downgraded, False, True)

    def test_walk_versions_alembic_all_false(self):
        upgraded = [mock.call(self.engine, v, with_data=True, alembic=True)
                    for v in self.vers]
        downgraded = []
        self._test_walk_versions_alembic(upgraded, downgraded, False, False)

    def test_walk_versions_alembic_all_true(self):
        up_with_data = [mock.call(self.engine, v, alembic=True, with_data=True)
                        for v in self.vers]
        up_without_data = [mock.call(self.engine, v, alembic=True)
                           for v in self.vers]
        upgraded = list(itertools.chain(*zip(up_with_data, up_without_data)))
        upgraded.extend([mock.call(self.engine, v, alembic=True)
                         for v in reversed(self.vers)])
        down_with_data = [mock.call(self.engine, self.down_vers[v],
                                    with_data=True, alembic=True,
                                    next_version=self.vers[v])
                          for v in range(3)]
        down_without_data = [mock.call(self.engine, self.down_vers[v],
                                       alembic=True, next_version=self.vers[v])
                             for v in reversed(range(3))]
        downgrade_list = list(itertools.chain(*zip(down_without_data,
                                              down_without_data)))
        downgraded = down_with_data + downgrade_list
        self._test_walk_versions_alembic(upgraded, downgraded, True, True)

    def test_walk_versions_alembic_True_False(self):
        with_data = [mock.call(self.engine, v, with_data=True, alembic=True)
                     for v in self.vers]
        without_data = [mock.call(self.engine, v, alembic=True)
                        for v in self.vers]
        upgraded = list(itertools.chain(*zip(with_data, without_data)))
        downgraded = [mock.call(self.engine, self.down_vers[v], with_data=True,
                                alembic=True, next_version=self.vers[v])
                      for v in range(3)]
        self._test_walk_versions_alembic(upgraded, downgraded, True, False)

    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def test_walk_versions_all_default(self, _migrate_up, _migrate_down):
        self.REPOSITORY.latest = 20
        self.migration_api.db_version.return_value = self.INIT_VERSION

        self._walk_versions()

        self.migration_api.version_control.assert_called_with(
            None, self.REPOSITORY, self.INIT_VERSION)
        self.migration_api.db_version.assert_called_with(
            None, self.REPOSITORY)

        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)
        upgraded = [mock.call(None, v, with_data=True) for v in versions]
        self.assertEqual(self._migrate_up.call_args_list, upgraded)

        downgraded = [mock.call(None, v - 1) for v in reversed(versions)]
        self.assertEqual(self._migrate_down.call_args_list, downgraded)

    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def test_walk_versions_all_true(self, _migrate_up, _migrate_down):
        self.REPOSITORY.latest = 20
        self.migration_api.db_version.return_value = self.INIT_VERSION

        self._walk_versions(self.engine, snake_walk=True, downgrade=True)

        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)
        upgraded = []
        for v in versions:
            upgraded.append(mock.call(self.engine, v, with_data=True))
            upgraded.append(mock.call(self.engine, v))
        upgraded.extend(
            [mock.call(self.engine, v) for v in reversed(versions)]
        )
        self.assertEqual(upgraded, self._migrate_up.call_args_list)

        downgraded_1 = [
            mock.call(self.engine, v - 1, with_data=True) for v in versions
        ]
        downgraded_2 = []
        for v in reversed(versions):
            downgraded_2.append(mock.call(self.engine, v - 1))
            downgraded_2.append(mock.call(self.engine, v - 1))
        downgraded = downgraded_1 + downgraded_2
        self.assertEqual(self._migrate_down.call_args_list, downgraded)

    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def test_walk_versions_true_false(self, _migrate_up, _migrate_down):
        self.REPOSITORY.latest = 20
        self.migration_api.db_version.return_value = self.INIT_VERSION

        self._walk_versions(self.engine, snake_walk=True, downgrade=False)

        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)

        upgraded = []
        for v in versions:
            upgraded.append(mock.call(self.engine, v, with_data=True))
            upgraded.append(mock.call(self.engine, v))
        self.assertEqual(upgraded, self._migrate_up.call_args_list)

        downgraded = [
            mock.call(self.engine, v - 1, with_data=True) for v in versions
        ]
        self.assertEqual(self._migrate_down.call_args_list, downgraded)

    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def test_walk_versions_all_false(self, _migrate_up, _migrate_down):
        self.REPOSITORY.latest = 20
        self.migration_api.db_version.return_value = self.INIT_VERSION

        self._walk_versions(self.engine, snake_walk=False, downgrade=False)

        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)

        upgraded = [
            mock.call(self.engine, v, with_data=True) for v in versions
        ]
        self.assertEqual(upgraded, self._migrate_up.call_args_list)


class TestSync(test_utils.BaseTestCase, migrate.SyncModelsWithMigrations):
    USER = 'openstack_citest'
    PASSWD = 'openstack_citest'
    DATABASE = 'openstack_citest'
    MODEL_BASE = fake.BASE
    DIALECT = 'mysql'

    def _test_sync_models_with_db(self, base, errors=None, exclude=None):
        connect_string = migrate._get_connect_string(self.DIALECT,
                                                     self.USER,
                                                     self.PASSWD,
                                                     self.DATABASE)
        if errors is not None:
            class FakeRefTable(base, fake._FakeRefTable):
                pass

        engine = sqlalchemy.create_engine(connect_string)
        base.metadata.create_all(engine)
        engine.dispose()
        if errors is not None:
            self.assertRaises(MismatchError,
                              self._test_list_of_tables,
                              self.DIALECT,
                              test_mode=True,
                              exclude_tables=exclude)
            self.assertEqual(errors, self.errors)
        else:
            self._test_list_of_tables(self.DIALECT, test_mode=True,
                                      exclude_tables=exclude)

    def test_sync_success(self):
        self._test_sync_models_with_db(fake.BASE)

    def test_sync_extra_tables_with_exclude(self):
        errors = ['Tables in `models`  have a difference '
                  'with migrations : (fake_table).']
        self._test_sync_models_with_db(fake.BASE_EXTRA_TABLES,
                                       errors, exclude=['extra_table'])

    def test_sync_indexes_difference(self):
        errors = ['Indexes in `fake_table` Indexes have a difference '
                  'with migrations : (col_cidr_idx,col_str_idx).']
        self._test_sync_models_with_db(fake.BASE_INDEXES_DIFF,
                                       errors)

    def test_sync_uniq_difference(self):
        errors = ['UniqueConstraint `fake_table.uniq_fake_table0col_fk0id` '
                  'declared in models is skipped in migrations.',
                  'Indexes in `fake_table` Indexes have a difference with '
                  'migrations : (UNIQ_col_fk0id).']
        self._test_sync_models_with_db(fake.BASE_UNIQ_DIFF,
                                       errors)

    def test_sync_fk_difference(self):
        errors = ['ForeignKey in `fake_table`  have a difference with '
                  'migrations : (col_fk2,col_fk).',
                  'Indexes in `fake_table` Indexes have a difference with '
                  'migrations : (col_fk2).']
        self._test_sync_models_with_db(fake.BASE_FK_DIFF,
                                       errors)

    def test_sync_extra_column(self):
        errors = ['Columns in `fake_table`  have a difference with migrations '
                  ': (col_fk3,col_fk2).']
        self._test_sync_models_with_db(fake.BASE_EXTRA_COLUMN,
                                       errors)

    def test_sync_wrong_column_type(self):
        errors = ['Wrong type for column `col_cidr` in `fake_table`: `CIDR`, '
                  'expected: `INTEGER`',
                  'Wrong length for column `col_cidr` in `fake_table` '
                  '(model: 43, db: None)']
        self._test_sync_models_with_db(fake.BASE_WRONG_TYPE,
                                       errors)

    def test_sync_wrong_index_order(self):
        errors = ['Indexes in `fake_table.col_cidr_idx` have wrong order: '
                  '(col_cidr,col_fk): expected (col_fk,col_cidr)']
        self._test_sync_models_with_db(fake.BASE_WRONG_INDEX_ORDER,
                                       errors)

    def test_sync_extra_nullable(self):
        errors = ['Wrong value for `nullable` attribute in '
                  '`fake_table.col_str` (models:False, db:True)']
        self._test_sync_models_with_db(fake.BASE_EXTRA_NULLABLE,
                                       errors)

    def test_sync_wrong_uniq_index(self):
        errors = ['Index `fake_table.uniq_fake_table0col_fk0id` should be '
                  'unique.']
        self._test_sync_models_with_db(fake.BASE_WRONG_UNIQ_INDEX,
                                       errors)

    def test_sync_wrong_uniq_name(self):
        errors = ['UniqueConstraint `fake_table.fake_table0col_fk0id` has a '
                  'wrong name. Expected:`uniq_fake_table0col_fk0id`']
        self.MODEL_BASE = fake.BASE_WRONG_UNIQ_NAME
        self._test_sync_models_with_db(fake.BASE_WRONG_UNIQ_NAME,
                                       errors)
        self.MODEL_BASE = fake.BASE
