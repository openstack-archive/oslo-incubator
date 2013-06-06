# Copyright 2013 Mirantis Inc.
# All Rights Reserved
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
#
# vim: tabstop=4 shiftwidth=4 softtabstop=4


import contextlib
import mock

from migrate import exceptions as migrate_exception
from migrate.versioning import api as versioning_api
import sqlalchemy

from openstack.common.db.sqlalchemy import migration_common as migration
from openstack.common.db.sqlalchemy import session as db_session
from openstack.common import exception as common_exception

from tests.unit.db.sqlalchemy import base


class TestMigrationCommon(base.DbTestCase):
    def setUp(self):
        super(TestMigrationCommon, self).setUp()

        migration._REPOSITORY = None
        self.abs_path = '/tmp'
        self.return_value = '/tmp/migrations'
        self.init_version = 1
        self.test_version = 123

        migration.Repository = mock.MagicMock()
        migration.Repository.return_value = self.return_value

    def test_find_migrate_repo_path_not_found(self):
        self.assertRaises(
            common_exception.NotFound,
            migration._find_migrate_repo,
            "/foo/bar/",
        )
        self.assertIsNone(migration._REPOSITORY)

    def test_find_migrate_repo_called_once(self):
        repository = migration._find_migrate_repo(self.abs_path)

        migration.Repository.assert_called_once_with(self.abs_path)
        self.assertEqual(migration._REPOSITORY, self.return_value)
        self.assertEqual(repository, self.return_value)

    def test_find_migrate_repo_called_few_times(self):
        repository1 = migration._find_migrate_repo(self.abs_path)
        repository2 = migration._find_migrate_repo(self.abs_path)

        migration.Repository.assert_called_once_with(self.abs_path)
        self.assertEqual(migration._REPOSITORY, self.return_value)
        self.assertEqual(repository1, self.return_value)
        self.assertEqual(repository2, self.return_value)

    def test_db_version_control(self):
        with contextlib.nested(
            mock.patch.object(migration, '_find_migrate_repo'),
            mock.patch.object(versioning_api, 'version_control'),
        ) as (mock_find_repo, mock_version_control):
            mock_find_repo.return_value = self.return_value

            version = migration.db_version_control(
                self.abs_path, self.test_version)

            self.assertEqual(version, self.test_version)
            mock_version_control.assert_called_once_with(
                db_session.get_engine(), self.return_value, self.test_version)

    def test_db_version_return(self):
        with mock.patch.object(versioning_api, 'db_version') as mock_db_ver:
            mock_db_ver.return_value = self.test_version

            ret_val = migration.db_version(self.abs_path, self.init_version)
            self.assertEqual(ret_val, self.test_version)

    def test_db_version_raise_not_controlled_error_first(self):
        with contextlib.nested(
            mock.patch.object(versioning_api, 'db_version'),
            mock.patch.object(migration, 'db_version_control'),
        ) as (mock_db_ver, mock_db_ver_control):

            mock_db_ver.side_effect = [
                migrate_exception.DatabaseNotControlledError('oups'),
                self.test_version]

            ret_val = migration.db_version(self.abs_path, self.init_version)
            self.assertEqual(ret_val, self.test_version)

    def test_db_version_raise_not_controlled_error_no_tables(self):
        with contextlib.nested(
            mock.patch.object(versioning_api, 'db_version'),
            mock.patch.object(sqlalchemy, 'MetaData'),
        ) as (mock_db_ver, mock_meta):
            mock_db_ver.side_effect = \
                migrate_exception.DatabaseNotControlledError('oups')
            my_meta = mock.MagicMock()
            my_meta.tables = {'a': 1, 'b': 2}
            mock_meta.return_value = my_meta

            self.assertRaises(
                common_exception.OpenstackException, migration.db_version,
                self.abs_path, self.init_version)

    def test_db_sync_wrong_version(self):
        self.assertRaises(
            common_exception.OpenstackException, migration.db_sync,
            self.abs_path, 'foo')

    def test_db_sync_upgrade(self):
        with contextlib.nested(
            mock.patch.object(migration, 'db_version'),
            mock.patch.object(migration, '_find_migrate_repo'),
            mock.patch.object(versioning_api, 'upgrade')
        ) as (mock_db_ver, mock_find_repo, mock_upgrade):

            mock_find_repo.return_value = self.return_value
            mock_db_ver.return_value = self.test_version - 1

            migration.db_sync(self.abs_path, self.test_version)

            mock_upgrade.assert_called_once_with(
                db_session.get_engine(), self.return_value, self.test_version)

    def test_db_sync_downgrade(self):
        with contextlib.nested(
            mock.patch.object(migration, 'db_version'),
            mock.patch.object(migration, '_find_migrate_repo'),
            mock.patch.object(versioning_api, 'downgrade')
        ) as (mock_db_ver, mock_find_repo, mock_downgrade):

            mock_find_repo.return_value = self.return_value
            mock_db_ver.return_value = self.test_version + 1

            migration.db_sync(self.abs_path, self.test_version)

            mock_downgrade.assert_called_once_with(
                db_session.get_engine(), self.return_value, self.test_version)
