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

import abc
import os

import alembic
from alembic import config as alembic_config
import alembic.migration as alembic_migration

from oslo.config import cfg

from openstack.common.db.sqlalchemy import migration
from openstack.common.db.sqlalchemy import session as db_session
from openstack.common import log as logging


_db_opts = [
    cfg.StrOpt('alembic_ini_path',
               default=None,
               help=('Full path to alembic.ini file.')),
    cfg.StrOpt('migrate_repo_path',
               default=None,
               help=('Full path to migrate_repo.')),
    cfg.IntOpt('init_version',
               default=1,
               help=('Initial database version.'))
]


cfg.CONF.register_opts(_db_opts, 'database')


LOG = logging.getLogger(__name__)


class MigrationExtensionBase(object):

    __metaclass__ = abc.ABCMeta

    #used to sort migration in logical order
    order = 0

    @classmethod
    def check_available(cls):
        """Used for availability verification of a plugin.

        :retval Boolean
        """
        return False

    @abc.abstractmethod
    def upgrade(self, version):
        pass

    @abc.abstractmethod
    def downgrade(self, version):
        pass

    @abc.abstractmethod
    def version(self):
        pass

    def revision(self, *args, **kwargs):
        raise NotImplementedError()

    def stamp(self, *args, **kwargs):
        raise NotImplementedError()

    def __cmp__(self, other):
        return self.order > other.order


class MigrateExtension(MigrationExtensionBase):

    order = 1

    def __init__(self):
        self.repository = cfg.CONF.database.migrate_repo_path

    @classmethod
    def check_available(cls):
        return os.path.exists(cfg.CONF.database.migrate_repo_path)

    def upgrade(self, version):
        version = None if version == 'head' else version
        return migration.db_sync(
            self.repository, version,
            init_version=cfg.CONF.database.init_version)

    def downgrade(self, version):
        try:
            #version for migrate should be valid int - else skip
            version = int(cfg.CONF.database.init_version if version
                          in ('base', None) else version)
            return migration.db_sync(
                self.repository, version,
                init_version=cfg.CONF.database.init_version)
        except ValueError:
            LOG.error(
                ('Migration number for migrate plugin should be valid '
                 'integer or empty if you want downgrade to initial state')
            )

    def version(self):
        return migration.db_version(
            self.repository, init_version=cfg.CONF.database.init_version)


class AlembicExtension(MigrationExtensionBase):

    order = 2

    @classmethod
    def check_available(cls):
        return os.path.exists(cfg.CONF.database.alembic_ini_path)

    def __init__(self):
        self.config = alembic_config.Config(cfg.CONF.database.alembic_ini_path)

    def upgrade(self, version):
        return alembic.command.upgrade(self.config, version or 'head')

    def downgrade(self, version):
        version = ('base' if isinstance(version, int)
                   or version is None else version)
        return alembic.command.downgrade(self.config, version)

    def version(self):
        conn = db_session.get_engine().connect()
        context = alembic_migration.MigrationContext.configure(conn)
        return context.get_current_revision()

    def revision(self, message=None, autogenerate=False):
        return alembic.command.revision(self.config, message=message,
                                        autogenerate=autogenerate)

    def stamp(self, revision):
        return alembic.command.stamp(self.config, revision=revision)
