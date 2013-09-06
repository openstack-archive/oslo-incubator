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

import mock
import testtools.matchers

from openstack.common.db.sqlalchemy import test_migrations as migrate
from openstack.common import log as logging

from tests import utils as test_utils

LOG = logging.getLogger(__name__)
MismatchError = testtools.matchers.MismatchError


class TestWalkVersions(test_utils.BaseTestCase, migrate.WalkVersionsMixin):
    MIGRATION_API = mock.MagicMock()
    REPOSITORY = mock.MagicMock()
    INIT_VERSION = 4
    ALEMBIC_CONFIG = mock.MagicMock()

    def setUp(self):
        super(TestWalkVersions, self).setUp()
        self.engine = mock.MagicMock()
        self.vers = ['1', '2', '3']
        self.down_vers = ['-1', '1', '2']

    @mock.patch('alembic.command.upgrade')
    @mock.patch('alembic.migration.MigrationContext.configure')
    def test_migrate_up_alembic(self, mock_conf, mock_upgrade):
        mock_conf.return_value.get_current_revision.return_value = 141
        self._migrate_up(self.engine, 141, alembic=True)
        self.assertEqual(mock_upgrade.call_args_list,
                         [mock.call(self.ALEMBIC_CONFIG, 141)])

    @mock.patch('alembic.command.upgrade')
    @mock.patch('alembic.migration.MigrationContext.configure')
    def test_migrate_up_alembic_failed(self, mock_conf, mock_upgrade):
        mock_conf.return_value.get_current_revision.return_value = 1
        self.assertRaises(MismatchError, self._migrate_up, self.engine,
                          141, alembic=True)
        self.assertEqual(mock_upgrade.call_args_list,
                         [mock.call(self.ALEMBIC_CONFIG, 141)])

    @mock.patch('alembic.command.upgrade')
    @mock.patch('alembic.migration.MigrationContext.configure')
    def test_migrate_up_alembic_with_data(self, mock_conf, mock_upgrade):
        mock_conf.return_value.get_current_revision.return_value = 141
        test_value = {"a": 1, "b": 2}
        self._pre_upgrade_141 = mock.MagicMock()
        self._pre_upgrade_141.return_value = test_value
        self._check_141 = mock.MagicMock()

        self._migrate_up(self.engine, 141, with_data=True, alembic=True)

        self._pre_upgrade_141.assert_called_with(self.engine)
        self._check_141.assert_called_with(self.engine, test_value)
        self.assertEqual(mock_upgrade.call_args_list,
                         [mock.call(self.ALEMBIC_CONFIG, 141)])

    @mock.patch('alembic.command.downgrade')
    @mock.patch('alembic.migration.MigrationContext.configure')
    def test_migrate_down_alembic(self, mock_conf, mock_downgrade):
        mock_conf.return_value.get_current_revision.return_value = 141
        self._migrate_down(self.engine, 141, alembic=True)
        self.assertEqual(mock_downgrade.call_args_list,
                         [mock.call(self.ALEMBIC_CONFIG, 141)])

    @mock.patch('alembic.command.downgrade')
    @mock.patch('alembic.migration.MigrationContext.configure')
    def test_migrate_down_alembic_failed(self, mock_conf, mock_downgrade):
        mock_conf.return_value.get_current_revision.return_value = 1
        self.assertRaises(MismatchError, self._migrate_down, self.engine,
                          141, alembic=True)
        self.assertEqual(mock_downgrade.call_args_list,
                         [mock.call(self.ALEMBIC_CONFIG, 141)])

    @mock.patch('alembic.command.downgrade')
    @mock.patch('alembic.migration.MigrationContext.configure')
    def test_migrate_down_alembic_with_data(self, mock_conf, mock_downgrade):
        mock_conf.return_value.get_current_revision.return_value = 141
        self._post_downgrade_123 = mock.MagicMock()

        self._migrate_down(self.engine, 141, with_data=True, alembic=True,
                           next_version='123')

        self._post_downgrade_123.assert_called_with(self.engine)
        self.assertEqual(mock_downgrade.call_args_list,
                         [mock.call(self.ALEMBIC_CONFIG, 141)])

    def test_migrate_up(self):
        self.MIGRATION_API.db_version.return_value = 141

        self._migrate_up(self.engine, 141)

        self.MIGRATION_API.upgrade.assert_called_with(
            self.engine, self.REPOSITORY, 141)
        self.MIGRATION_API.db_version.assert_called_with(
            self.engine, self.REPOSITORY)

    def test_migrate_up_with_data(self):
        test_value = {"a": 1, "b": 2}
        self.MIGRATION_API.db_version.return_value = 141
        self._pre_upgrade_141 = mock.MagicMock()
        self._pre_upgrade_141.return_value = test_value
        self._check_141 = mock.MagicMock()

        self._migrate_up(self.engine, 141, True)

        self._pre_upgrade_141.assert_called_with(self.engine)
        self._check_141.assert_called_with(self.engine, test_value)

    def test_migrate_down(self):
        self.MIGRATION_API.db_version.return_value = 42

        self.assertTrue(self._migrate_down(self.engine, 42))
        self.MIGRATION_API.db_version.assert_called_with(
            self.engine, self.REPOSITORY)

    def test_migrate_down_not_implemented(self):
        self.MIGRATION_API.downgrade.side_effect = NotImplementedError
        self.assertFalse(self._migrate_down(self.engine, 42))

    def test_migrate_down_with_data(self):
        self._post_downgrade_043 = mock.MagicMock()
        self.MIGRATION_API.db_version.return_value = 42
        self.MIGRATION_API.downgrade = mock.MagicMock()
        self._migrate_down(self.engine, 42, with_data=True, next_version=43)
        self._post_downgrade_043.assert_called_with(self.engine)

    @mock.patch.object(migrate.WalkVersionsMixin, '_get_alembic_versions',
                       return_value=['1', '2', '3'])
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def _test_walk_versions_alembic(self, upgraded, downgraded, snake,
                                    downgrade, versions, _migrate_up,
                                    _migrate_down):
        self.engine.url = 'fake_url'
        self._walk_versions(self.engine, snake, downgrade, alembic=True)
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
        self.MIGRATION_API.db_version.return_value = self.INIT_VERSION

        self._walk_versions()

        self.MIGRATION_API.version_control.assert_called_with(
            None, self.REPOSITORY, self.INIT_VERSION)
        self.MIGRATION_API.db_version.assert_called_with(
            None, self.REPOSITORY)

        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)
        upgraded = [mock.call(None, v, alembic=False,
                              with_data=True) for v in versions]
        self.assertEqual(self._migrate_up.call_args_list, upgraded)

        downgraded = [mock.call(None, v - 1, alembic=False,
                                next_version=v) for v in reversed(versions)]
        self.assertEqual(self._migrate_down.call_args_list, downgraded)

    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def test_walk_versions_all_true(self, _migrate_up, _migrate_down):
        self.REPOSITORY.latest = 20
        self.MIGRATION_API.db_version.return_value = self.INIT_VERSION

        self._walk_versions(self.engine, snake_walk=True, downgrade=True)

        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)
        upgraded = []
        for v in versions:
            upgraded.append(mock.call(self.engine, v, alembic=False,
                                      with_data=True))
            upgraded.append(mock.call(self.engine, v, alembic=False))
        upgraded.extend(
            [mock.call(self.engine, v,
                       alembic=False) for v in reversed(versions)]
        )
        self.assertEqual(upgraded, self._migrate_up.call_args_list)

        downgraded_1 = [
            mock.call(self.engine, v - 1, with_data=True,
                      alembic=False, next_version=v) for v in versions
        ]
        downgraded_2 = []
        for v in reversed(versions):
            downgraded_2.append(mock.call(self.engine, v - 1, alembic=False,
                                          next_version=v))
            downgraded_2.append(mock.call(self.engine, v - 1, alembic=False,
                                          next_version=v))
        downgraded = downgraded_1 + downgraded_2
        self.assertEqual(self._migrate_down.call_args_list, downgraded)

    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def test_walk_versions_true_false(self, _migrate_up, _migrate_down):
        self.REPOSITORY.latest = 20
        self.MIGRATION_API.db_version.return_value = self.INIT_VERSION

        self._walk_versions(self.engine, snake_walk=True, downgrade=False)

        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)

        upgraded = []
        for v in versions:
            upgraded.append(mock.call(self.engine, v, alembic=False,
                                      with_data=True))
            upgraded.append(mock.call(self.engine, v, alembic=False))
        self.assertEqual(upgraded, self._migrate_up.call_args_list)

        downgraded = [
            mock.call(self.engine, v - 1, with_data=True,
                      alembic=False, next_version=v) for v in versions
        ]
        self.assertEqual(self._migrate_down.call_args_list, downgraded)

    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def test_walk_versions_all_false(self, _migrate_up, _migrate_down):
        self.REPOSITORY.latest = 20
        self.MIGRATION_API.db_version.return_value = self.INIT_VERSION

        self._walk_versions(self.engine, snake_walk=False, downgrade=False)

        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)

        upgraded = [
            mock.call(self.engine, v, alembic=False,
                      with_data=True) for v in versions
        ]
        self.assertEqual(upgraded, self._migrate_up.call_args_list)
