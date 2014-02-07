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

import os
import shutil
import subprocess
import tempfile

from alembic import command as alembic_command
from alembic import config
from alembic import script
import mock
import sqlalchemy

from openstack.common.db.sqlalchemy.migration_cli import ext_alembic
from openstack.common.db.sqlalchemy.migration_cli import ext_migrate
from openstack.common.db.sqlalchemy.migration_cli import manager
from openstack.common import test


class MockWithCmp(mock.MagicMock):

    order = 0

    def __cmp__(self, other):
        return self.order > other.order


class TestAlembicExtension(test.BaseTestCase):

    def setUp(self):
        temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp_dir)

        config_filename = os.path.join(temp_dir, 'alembic_test.ini')
        alembic_tempdir = os.path.join(temp_dir, 'alembic_test')
        alembic_env_py = os.path.join(alembic_tempdir, 'env.py')

        self.alembic_config = config.Config(config_filename)
        alembic_command.init(self.alembic_config, alembic_tempdir)

        #delete fileConfig from alembic env.py
        subprocess.call(
            '/bin/sed -i /fileConfig\(config/d %s' % alembic_env_py,
            shell=True)

        db_url = 'sqlite:///{path}/{dbname}'.format(
            path=temp_dir, dbname='alembic_test.db')
        self.alembic_config.set_main_option('sqlalchemy.url', db_url)

        migration_config = {'alembic_ini_path': config_filename}
        engine = sqlalchemy.create_engine(db_url)

        self.alembic = ext_alembic.AlembicExtension(engine,
                                                    migration_config)
        self.alembic.revision(message='test')
        super(TestAlembicExtension, self).setUp()

    def yield_revisions(self):
        script_dir = script.ScriptDirectory.from_config(self.alembic_config)
        for revision in script_dir.walk_revisions():
            yield revision.revision

    def test_check_enabled_true(self):
        """Verifies that enabled returns True on non empty
        alembic_ini_path conf variable
        """
        self.assertTrue(self.alembic.enabled)

    def test_upgrade(self):
        for revision in self.yield_revisions():
            self.alembic.upgrade(revision)
            self.assertEqual(self.alembic.version(), revision)

    def test_upgreade_head(self):
        self.alembic.upgrade('head')
        revisions = list(self.yield_revisions())
        self.assertEqual(self.alembic.version(), revisions[-1])

    def test_downgrade(self):
        self.alembic.upgrade('head')
        self.assertIsNotNone(self.alembic.version())
        self.alembic.downgrade(None)
        self.assertIsNone(self.alembic.version())

    def test_downgrade_base(self):
        self.alembic.upgrade('head')
        self.assertIsNotNone(self.alembic.version())
        self.alembic.downgrade('base')
        self.assertIsNone(self.alembic.version())

    def test_revision(self):
        self.alembic.revision(message='test', autogenerate=False)
        list_revisions = list(self.yield_revisions())
        self.assertEqual(len(list_revisions), 2)

    def test_stamp_head(self):
        self.alembic.stamp('head')
        list_revisions = list(self.yield_revisions())
        self.assertEqual(self.alembic.version(), list_revisions[-1])

    def test_version(self):
        self.assertIsNone(self.alembic.version())
        self.alembic.upgrade('head')
        self.assertIsNotNone(self.alembic.version())


@mock.patch(('openstack.common.db.sqlalchemy.migration_cli.'
             'ext_migrate.migration'))
class TestMigrateExtension(test.BaseTestCase):

    def setUp(self):
        self.migration_config = {'migration_repo_path': '.',
                                 'db_url': 'sqlite://'}
        self.engine = mock.Mock()
        self.migrate = ext_migrate.MigrateExtension(self.engine,
                                                    self.migration_config)
        super(TestMigrateExtension, self).setUp()

    def test_check_enabled_true(self, migration):
        self.assertTrue(self.migrate.enabled)

    def test_check_enabled_false(self, migration):
        self.migration_config['migration_repo_path'] = ''
        migrate = ext_migrate.MigrateExtension(self.engine,
                                               self.migration_config)
        self.assertFalse(migrate.enabled)

    def test_upgrade_head(self, migration):
        self.migrate.upgrade('head')
        migration.db_sync.assert_called_once_with(
            self.migrate.engine, self.migrate.repository, None, init_version=0)

    def test_upgrade_normal(self, migration):
        self.migrate.upgrade(111)
        migration.db_sync.assert_called_once_with(
            mock.ANY, self.migrate.repository, 111, init_version=0)

    def test_downgrade_init_version_from_base(self, migration):
        self.migrate.downgrade('base')
        migration.db_sync.assert_called_once_with(
            self.migrate.engine, self.migrate.repository, mock.ANY,
            init_version=mock.ANY)

    def test_downgrade_init_version_from_none(self, migration):
        self.migrate.downgrade(None)
        migration.db_sync.assert_called_once_with(
            self.migrate.engine, self.migrate.repository, mock.ANY,
            init_version=mock.ANY)

    def test_downgrade_normal(self, migration):
        self.migrate.downgrade(101)
        migration.db_sync.assert_called_once_with(
            self.migrate.engine, self.migrate.repository, 101, init_version=0)

    def test_version(self, migration):
        self.migrate.version()
        migration.db_version.assert_called_once_with(
            self.migrate.engine, self.migrate.repository, init_version=0)

    def test_change_init_version(self, migration):
        self.migration_config['init_version'] = 101
        migrate = ext_migrate.MigrateExtension(self.engine,
                                               self.migration_config)
        migrate.downgrade(None)
        migration.db_sync.assert_called_once_with(
            migrate.engine,
            self.migrate.repository,
            self.migration_config['init_version'],
            init_version=self.migration_config['init_version'])


class TestMigrationManager(test.BaseTestCase):

    def setUp(self):
        self.migration_config = {'alembic_ini_path': '.',
                                 'migrate_repo_path': '.'}
        self.engine = mock.Mock()
        self.manager_patcher = mock.patch(
            'openstack.common.db.sqlalchemy.migration_cli.manager.'
            'enabled.EnabledExtensionManager')
        self.ext_manager = self.manager_patcher.start()
        self.plugin = mock.Mock()
        self.ext_manager().extensions = [self.plugin]
        self.addCleanup(self.manager_patcher.stop)
        self.migration_manager = manager.MigrationManager(
            self.migration_config, engine=self.engine)
        self.ext = mock.Mock()
        self.migration_manager._manager.extensions = [self.ext]
        super(TestMigrationManager, self).setUp()

    def test_initialized(self):
        self.ext_manager.assert_called_with(
            manager.MIGRATION_NAMESPACE,
            manager.check_plugin_enabled,
            invoke_on_load=True,
            invoke_args=(self.engine, self.migration_config))

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
        self.engine = mock.Mock()
        self.manager_patcher = mock.patch(
            'openstack.common.db.sqlalchemy.migration_cli.manager.'
            'enabled.EnabledExtensionManager')
        self.ext_manager = self.manager_patcher.start()
        self.addCleanup(self.manager_patcher.stop)

        self.first_ext = MockWithCmp()
        self.first_ext.obj.order = 1
        self.first_ext.obj.upgrade.return_value = 100
        self.first_ext.obj.downgrade.return_value = 0
        self.second_ext = MockWithCmp()
        self.second_ext.obj.order = 2
        self.second_ext.obj.upgrade.return_value = 200
        self.second_ext.obj.downgrade.return_value = 100
        self.ext_manager().extensions = [self.first_ext, self.second_ext]

        self.migration_manager = manager.MigrationManager(
            self.migration_config, engine=self.engine)
        super(TestMigrationRightOrder, self).setUp()

    def test_upgrade_right_order(self):
        results = self.migration_manager.upgrade(None)
        self.assertEqual(results, [100, 200])

    def test_downgrade_right_order(self):
        results = self.migration_manager.downgrade(None)
        self.assertEqual(results, [100, 0])
