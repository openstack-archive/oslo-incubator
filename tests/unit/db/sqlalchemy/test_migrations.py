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

import mock
from oslotest import base as test_base

from openstack.common.db.sqlalchemy import test_migrations as migrate


class TestWalkVersions(test_base.BaseTestCase, migrate.WalkVersionsMixin):
    def setUp(self):
        super(TestWalkVersions, self).setUp()
        self.migration_api = mock.MagicMock()
        self.engine = mock.MagicMock()
        self.REPOSITORY = mock.MagicMock()
        self.INIT_VERSION = 4

    def test_migrate_up(self):
        self.migration_api.db_version.return_value = 141

        self._migrate_up(141)

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

        self._migrate_up(141, True)

        self._pre_upgrade_141.assert_called_with(self.engine)
        self._check_141.assert_called_with(self.engine, test_value)

    def test_migrate_down(self):
        self.migration_api.db_version.return_value = 42

        self.assertTrue(self._migrate_down(42))
        self.migration_api.db_version.assert_called_with(
            self.engine, self.REPOSITORY)

    def test_migrate_down_not_implemented(self):
        self.migration_api.downgrade.side_effect = NotImplementedError
        self.assertFalse(self._migrate_down(self.engine, 42))

    def test_migrate_down_with_data(self):
        self._post_downgrade_043 = mock.MagicMock()
        self.migration_api.db_version.return_value = 42

        self._migrate_down(42, True)

        self._post_downgrade_043.assert_called_with(self.engine)

    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def test_walk_versions_all_default(self, _migrate_up, _migrate_down):
        self.REPOSITORY.latest = 20
        self.migration_api.db_version.return_value = self.INIT_VERSION

        self._walk_versions()

        self.migration_api.version_control.assert_called_with(
            self.engine, self.REPOSITORY, self.INIT_VERSION)
        self.migration_api.db_version.assert_called_with(
            self.engine, self.REPOSITORY)

        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)
        upgraded = [mock.call(v, with_data=True)
                    for v in versions]
        self.assertEqual(self._migrate_up.call_args_list, upgraded)

        downgraded = [mock.call(v - 1) for v in reversed(versions)]
        self.assertEqual(self._migrate_down.call_args_list, downgraded)

    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def test_walk_versions_all_true(self, _migrate_up, _migrate_down):
        self.REPOSITORY.latest = 20
        self.migration_api.db_version.return_value = self.INIT_VERSION

        self._walk_versions(snake_walk=True, downgrade=True)

        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)
        upgraded = []
        for v in versions:
            upgraded.append(mock.call(v, with_data=True))
            upgraded.append(mock.call(v))
        upgraded.extend([mock.call(v) for v in reversed(versions)])
        self.assertEqual(upgraded, self._migrate_up.call_args_list)

        downgraded_1 = [mock.call(v - 1, with_data=True) for v in versions]
        downgraded_2 = []
        for v in reversed(versions):
            downgraded_2.append(mock.call(v - 1))
            downgraded_2.append(mock.call(v - 1))
        downgraded = downgraded_1 + downgraded_2
        self.assertEqual(self._migrate_down.call_args_list, downgraded)

    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def test_walk_versions_true_false(self, _migrate_up, _migrate_down):
        self.REPOSITORY.latest = 20
        self.migration_api.db_version.return_value = self.INIT_VERSION

        self._walk_versions(snake_walk=True, downgrade=False)

        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)

        upgraded = []
        for v in versions:
            upgraded.append(mock.call(v, with_data=True))
            upgraded.append(mock.call(v))
        self.assertEqual(upgraded, self._migrate_up.call_args_list)

        downgraded = [mock.call(v - 1, with_data=True) for v in versions]
        self.assertEqual(self._migrate_down.call_args_list, downgraded)

    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_up')
    @mock.patch.object(migrate.WalkVersionsMixin, '_migrate_down')
    def test_walk_versions_all_false(self, _migrate_up, _migrate_down):
        self.REPOSITORY.latest = 20
        self.migration_api.db_version.return_value = self.INIT_VERSION

        self._walk_versions(snake_walk=False, downgrade=False)

        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)

        upgraded = [mock.call(v, with_data=True) for v in versions]
        self.assertEqual(upgraded, self._migrate_up.call_args_list)
