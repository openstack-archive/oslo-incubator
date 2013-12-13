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


import contextlib
import os
import tempfile

from migrate import exceptions as migrate_exception
from migrate.versioning import api as versioning_api
import mock
import sqlalchemy

from openstack.common.db import exception as db_exception
from openstack.common.db.sqlalchemy import migration
from openstack.common.db.sqlalchemy import session as db_session
from openstack.common import test


class TestMigrationCommon(test.DbTestCase):
    def setUp(self):
        super(TestMigrationCommon, self).setUp()

        migration._REPOSITORY = None
        self.path = tempfile.mkdtemp('test_migration')
        self.return_value = '/home/openstack/migrations'
        self.init_version = 1
        self.test_version = 123

        self.patcher_repo = mock.patch.object(migration, 'Repository')
        self.repository = self.patcher_repo.start()
        self.repository.return_value = self.return_value

        self.mock_api_db = mock.patch.object(versioning_api, 'db_version')
        self.mock_api_db_version = self.mock_api_db.start()
        self.mock_api_db_version.return_value = self.test_version

    def tearDown(self):
        os.rmdir(self.path)
        self.mock_api_db.stop()
        self.patcher_repo.stop()
        super(TestMigrationCommon, self).tearDown()

    def test_find_migrate_repo_path_not_found(self):
        self.assertRaises(
            db_exception.DbMigrationError,
            migration._find_migrate_repo,
            "/foo/bar/",
        )
        self.assertIsNone(migration._REPOSITORY)

    def test_find_migrate_repo_called_once(self):
        my_repository = migration._find_migrate_repo(self.path)

        self.repository.assert_called_once_with(self.path)
        self.assertEqual(migration._REPOSITORY, self.return_value)
        self.assertEqual(my_repository, self.return_value)

    def test_find_migrate_repo_called_few_times(self):
        repository1 = migration._find_migrate_repo(self.path)
        repository2 = migration._find_migrate_repo(self.path)

        self.repository.assert_called_once_with(self.path)
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
                self.path, self.test_version)

            self.assertEqual(version, self.test_version)
            mock_version_control.assert_called_once_with(
                db_session.get_engine(), self.return_value, self.test_version)

    def test_db_version_return(self):
        ret_val = migration.db_version(self.path, self.init_version)
        self.assertEqual(ret_val, self.test_version)

    def test_db_version_raise_not_controlled_error_first(self):
        with mock.patch.object(migration, 'db_version_control') as mock_ver:

            self.mock_api_db_version.side_effect = [
                migrate_exception.DatabaseNotControlledError('oups'),
                self.test_version]

            ret_val = migration.db_version(self.path, self.init_version)
            self.assertEqual(ret_val, self.test_version)
            mock_ver.assert_called_once_with(self.path, self.init_version)

    def test_db_version_raise_not_controlled_error_no_tables(self):
        with mock.patch.object(sqlalchemy, 'MetaData') as mock_meta:
            self.mock_api_db_version.side_effect = \
                migrate_exception.DatabaseNotControlledError('oups')
            my_meta = mock.MagicMock()
            my_meta.tables = {'a': 1, 'b': 2}
            mock_meta.return_value = my_meta

            self.assertRaises(
                db_exception.DbMigrationError, migration.db_version,
                self.path, self.init_version)

    def test_db_sync_wrong_version(self):
        self.assertRaises(
            db_exception.DbMigrationError, migration.db_sync, self.path, 'foo')

    def test_db_sync_upgrade(self):
        init_ver = 55
        with contextlib.nested(
            mock.patch.object(migration, '_find_migrate_repo'),
            mock.patch.object(versioning_api, 'upgrade')
        ) as (mock_find_repo, mock_upgrade):

            mock_find_repo.return_value = self.return_value
            self.mock_api_db_version.return_value = self.test_version - 1

            migration.db_sync(self.path, self.test_version, init_ver)

            mock_upgrade.assert_called_once_with(
                db_session.get_engine(), self.return_value, self.test_version)

    def test_db_sync_downgrade(self):
        with contextlib.nested(
            mock.patch.object(migration, '_find_migrate_repo'),
            mock.patch.object(versioning_api, 'downgrade')
        ) as (mock_find_repo, mock_downgrade):

            mock_find_repo.return_value = self.return_value
            self.mock_api_db_version.return_value = self.test_version + 1

            migration.db_sync(self.path, self.test_version)

            mock_downgrade.assert_called_once_with(
                db_session.get_engine(), self.return_value, self.test_version)
