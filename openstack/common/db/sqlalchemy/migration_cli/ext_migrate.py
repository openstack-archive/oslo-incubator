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

from oslo.config import cfg

from openstack.common.db.sqlalchemy import migration
from openstack.common.db.sqlalchemy.migration_cli import ext_base
from openstack.common.gettextutils import _  # noqa
from openstack.common import log as logging


CONF = cfg.CONF

LOG = logging.getLogger(__name__)


class MigrateExtension(ext_base.MigrationExtensionBase):

    order = 1

    def __init__(self):
        self.repository = CONF.database.migrate_repo_path

    @classmethod
    def check_available(cls):
        return os.path.exists(CONF.database.migrate_repo_path)

    def upgrade(self, version):
        version = None if version == 'head' else version
        return migration.db_sync(
            self.repository, version,
            init_version=CONF.database.init_version)

    def downgrade(self, version):
        try:
            #version for migrate should be valid int - else skip
            version = int(CONF.database.init_version
                          if version in ('base', None) else version)
            return migration.db_sync(
                self.repository, version,
                init_version=CONF.database.init_version)
        except ValueError:
            LOG.error(
                _('Migration number for migrate plugin should be valid '
                  'integer or empty, in case you want downgrade'
                  ' to initial state')
            )

    def version(self):
        return migration.db_version(
            self.repository, init_version=cfg.CONF.database.init_version)
