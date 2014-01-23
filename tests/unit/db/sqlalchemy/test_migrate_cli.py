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

from openstack.common.db.sqlalchemy.migration_cli import ext_alembic
from openstack.common.db.sqlalchemy.migration_cli import ext_migrate
from openstack.common.db.sqlalchemy.migration_cli import manager
from openstack.common import test


class MockWithCmp(mock.MagicMock):

    order = 0

    def __cmp__(self, other):
        return self.order > other.order


@mock.patch(('openstack.common.db.sqlalchemy.migration_cli.'
             'ext_alembic.alembic.command'))
class TestAlembicExtension(test.BaseTestCase):

    def setUp(self):
        self.migration_config = {'alembic_ini_path': '.',
                                 'db_url': 'sqlite://'}
        self.alembic = ext_alembic.AlembicExtension(self.migration_config)
        super(TestAlembicExtension, self).setUp()

    def test_check_enabled_true(self, command):
        """Verifies that enabled returns True on non empty
        alembic_ini_path conf variable
        """
        self.assertTrue(self.alembic.enabled)

    def test_check_enabled_false(self, command):
        """Verifies enabled returns False on empty
        alembic_ini_path variable
        """
        self.migration_config['alembic_ini_path'] = ''
        alembic = ext_alembic.AlembicExtension(self.migration_config)
        self.assertFalse(alembic.enabled)

    def test_upgrade_none(self, command):
        self.alembic.upgrade(None)
        command.upgrade.assert_called_once_with(self.alembic.config, 'head')

    def test_upgrade_normal(self, command):
        self.alembic.upgrade('131daa')
        command.upgrade.assert_called_once_with(self.alembic.config, '131daa')

    def test_downgrade_none(self, command):
        self.alembic.downgrade(None)
        command.downgrade.assert_called_once_with(self.alembic.config, 'base')

    def test_downgrade_int(self, command):
        self.alembic.downgrade(111)
        command.downgrade.assert_called_once_with(self.alembic.config, 'base')

    def test_downgrade_normal(self, command):
        self.alembic.downgrade('131daa')
        command.downgrade.assert_called_once_with(
            self.alembic.config, '131daa')

    def test_revision(self, command):
        self.alembic.revision(message='test', autogenerate=True)
        command.revision.assert_called_once_with(
            self.alembic.config, message='test', autogenerate=True)

    def test_stamp(self, command):
        self.alembic.stamp('stamp')
        command.stamp.assert_called_once_with(
            self.alembic.config, revision='stamp')

    def test_version(self, command):
        version = self.alembic.version()
        self.assertIsNone(version)


@mock.patch(('openstack.common.db.sqlalchemy.migration_cli.'
             'ext_migrate.migration'))
class TestMigrateExtension(test.BaseTestCase):

    def setUp(self):
        self.migration_config = {'migration_repo_path': '.'}
        self.migrate = ext_migrate.MigrateExtension(self.migration_config)
        super(TestMigrateExtension, self).setUp()

    def test_check_enabled_true(self, migration):
        self.assertTrue(self.migrate.enabled)

    def test_check_enabled_false(self, migration):
        self.migration_config['migration_repo_path'] = ''
        migrate = ext_migrate.MigrateExtension(self.migration_config)
        self.assertFalse(migrate.enabled)

    def test_upgrade_head(self, migration):
        self.migrate.upgrade('head')
        migration.db_sync.assert_called_once_with(
            self.migrate.repository, None, init_version=0)

    def test_upgrade_normal(self, migration):
        self.migrate.upgrade(111)
        migration.db_sync.assert_called_once_with(
            self.migrate.repository, 111, init_version=0)

    def test_downgrade_init_version_from_base(self, migration):
        self.migrate.downgrade('base')
        migration.db_sync.assert_called_once_with(
            self.migrate.repository, mock.ANY,
            init_version=mock.ANY)

    def test_downgrade_init_version_from_none(self, migration):
        self.migrate.downgrade(None)
        migration.db_sync.assert_called_once_with(
            self.migrate.repository, mock.ANY,
            init_version=mock.ANY)

    def test_downgrade_normal(self, migration):
        self.migrate.downgrade(101)
        migration.db_sync.assert_called_once_with(
            self.migrate.repository, 101, init_version=0)

    def test_version(self, migration):
        self.migrate.version()
        migration.db_version.assert_called_once_with(
            self.migrate.repository, init_version=0)

    def test_change_init_version(self, migration):
        self.migration_config['init_version'] = 101
        migrate = ext_migrate.MigrateExtension(self.migration_config)
        migrate.downgrade(None)
        migration.db_sync.assert_called_once_with(
            self.migrate.repository,
            self.migration_config['init_version'],
            init_version=self.migration_config['init_version'])


class TestMigrationManager(test.BaseTestCase):

    def setUp(self):
        self.migration_config = {'alembic_ini_path': '.',
                                 'migrate_repo_path': '.'}
        self.migration_manager = manager.MigrationManager(
            self.migration_config)
        self.ext = mock.Mock()
        self.migration_manager._manager.extensions = [self.ext]
        super(TestMigrationManager, self).setUp()

    def test_manager_update(self):
        self.migration_manager.upgrade('head')
        self.ext.obj.upgrade.assert_called_once_with('head')

    def test_manager_update_revision_none(self):
        self.migration_manager.upgrade(None)
        self.ext.obj.upgrade.assert_called_once_with(None)

    def test_downgrade_normal_revision(self):
        self.migration_manager.downgrade('111abcd')
        self.ext.obj.downgrade.assert_called_once_with('111abcd')

    def test_version(self):
        self.migration_manager.version()
        self.ext.obj.version.assert_called_once_with()

    def test_revision_message_autogenerate(self):
        self.migration_manager.revision('test', True)
        self.ext.obj.revision.assert_called_once_with('test', True)

    def test_revision_only_message(self):
        self.migration_manager.revision('test', False)
        self.ext.obj.revision.assert_called_once_with('test', False)

    def test_stamp(self):
        self.migration_manager.stamp('stamp')
        self.ext.obj.stamp.assert_called_once_with('stamp')


class TestMigrationRightOrder(test.BaseTestCase):

    def setUp(self):
        self.migration_config = {'alembic_ini_path': '.',
                                 'migrate_repo_path': '.'}
        self.migration_manager = manager.MigrationManager(
            self.migration_config)
        self.first_ext = MockWithCmp()
        self.first_ext.obj.order = 1
        self.first_ext.obj.upgrade.return_value = 100
        self.first_ext.obj.downgrade.return_value = 0
        self.second_ext = MockWithCmp()
        self.second_ext.obj.order = 2
        self.second_ext.obj.upgrade.return_value = 200
        self.second_ext.obj.downgrade.return_value = 100
        self.migration_manager._manager.extensions = [self.first_ext,
                                                      self.second_ext]
        super(TestMigrationRightOrder, self).setUp()

    def test_upgrade_right_order(self):
        results = self.migration_manager.upgrade(None)
        self.assertEqual(results, [100, 200])

    def test_downgrade_right_order(self):
        results = self.migration_manager.downgrade(None)
        self.assertEqual(results, [100, 0])
