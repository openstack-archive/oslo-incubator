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

import os

import alembic
from alembic import config as alembic_config
import alembic.migration as alembic_migration
from oslo.config import cfg

from openstack.common.db.sqlalchemy.migration_cli import ext_base
from openstack.common.db.sqlalchemy import session as db_session


CONF = cfg.CONF


class AlembicExtension(ext_base.MigrationExtensionBase):

    order = 2

    @classmethod
    def check_available(cls):
        return os.path.exists(cfg.CONF.database.alembic_ini_path)

    def __init__(self):
        self.config = alembic_config.Config(cfg.CONF.database.alembic_ini_path)

    def upgrade(self, version):
        return alembic.command.upgrade(self.config, version or 'head')

    def downgrade(self, version):
        version = ('base'
                   if isinstance(version, int) or version is None
                   else version)
        return alembic.command.downgrade(self.config, version)

    def version(self):
        engine = db_session.get_engine()
        with engine.connect() as conn:
            context = alembic_migration.MigrationContext.configure(conn)
            return context.get_current_revision()

    def revision(self, message=None, autogenerate=False):
        return alembic.command.revision(self.config, message=message,
                                        autogenerate=autogenerate)

    def stamp(self, revision):
        return alembic.command.stamp(self.config, revision=revision)
