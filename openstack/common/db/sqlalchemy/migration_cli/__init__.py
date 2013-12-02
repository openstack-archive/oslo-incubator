# Copyright 2013 Mirantis Inc.
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

from oslo.config import cfg

from openstack.common.db.sqlalchemy.migration_cli import manager


_db_opts = [
    cfg.StrOpt('alembic_ini_path',
               default='',
               help='Full path to alembic.ini file.'),
    cfg.StrOpt('migrate_repo_path',
               default='',
               help='Full path to migrate_repo.'),
    cfg.IntOpt('init_version',
               default=0,
               help='Initial database version.')
]

CONF = cfg.CONF

CONF.register_opts(_db_opts, 'database')


def get_migration_manager():
    return manager.MigrationManager(
        manager.MIGRATION_NAMESPACE, invoke_on_load=True)
