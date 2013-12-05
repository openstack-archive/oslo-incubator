# Copyright 2013 OpenStack Foundation
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
import sys

from oslo.config import cfg

from openstack.common.db.sqlalchemy.migration_cli import manager

_MIGRATION_MANAGER = None


def get_migration_manager():
    global _MIGRATION_MANAGER
    if _MIGRATION_MANAGER is None:
        _MIGRATION_MANAGER = manager.MigrationManager(
            manager.MIGRATION_NAMESPACE, invoke_on_load=True)
    return _MIGRATION_MANAGER


def main():
    migration_manager = get_migration_manager()
    command_opt = cfg.SubCommandOpt(
        'command',
        title='Command',
        help=('Available commands'),
        handler=migration_manager.initialize_parsers
    )
    cfg.CONF.register_cli_opt(command_opt)
    cfg.CONF()
    cfg.CONF.command.func()
    sys.exit()
