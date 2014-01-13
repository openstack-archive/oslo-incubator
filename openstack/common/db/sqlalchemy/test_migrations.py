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

import logging

from openstack.common.gettextutils import _LE

LOG = logging.getLogger(__name__)


class WalkVersionsMixin(object):

    def _walk_versions(self, snake_walk=False, downgrade=True):
        # Determine latest version script from the repo, then
        # upgrade from 1 through to the latest, with no data
        # in the databases. This just checks that the schema itself
        # upgrades successfully.

        # Place the database under version control
        self.migration_api.version_control(self.engine, self.REPOSITORY,
                                           self.INIT_VERSION)
        self.assertEqual(self.INIT_VERSION,
                         self.migration_api.db_version(self.engine,
                                                       self.REPOSITORY))

        LOG.debug('latest version is %s' % self.REPOSITORY.latest)
        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)

        for version in versions:
            # upgrade -> downgrade -> upgrade
            self._migrate_up(version, with_data=True)
            if snake_walk:
                downgraded = self._migrate_down(version - 1, with_data=True)
                if downgraded:
                    self._migrate_up(version)

        if downgrade:
            # Now walk it back down to 0 from the latest, testing
            # the downgrade paths.
            for version in reversed(versions):
                # downgrade -> upgrade -> downgrade
                downgraded = self._migrate_down(version - 1)

                if snake_walk and downgraded:
                    self._migrate_up(version)
                    self._migrate_down(version - 1)

    def _migrate_down(self, version, with_data=False):

        try:
            self.migration_api.downgrade(self.engine, self.REPOSITORY, version)
        except NotImplementedError:
            # NOTE(sirp): some migrations, namely release-level
            # migrations, don't support a downgrade.
            return False

        self.assertEqual(version, self.migration_api.db_version(
            self.engine, self.REPOSITORY))

        # NOTE(sirp): `version` is what we're downgrading to (i.e. the 'target'
        # version). So if we have any downgrade checks, they need to be run for
        # the previous (higher numbered) migration.
        if with_data:
            post_downgrade = getattr(
                self, "_post_downgrade_%03d" % (version + 1), None)
            if post_downgrade:
                post_downgrade(self.engine)

        return True

    def _migrate_up(self, version, with_data=False):
        """migrate up to a new version of the db.

        We allow for data insertion and post checks at every
        migration version with special _pre_upgrade_### and
        _check_### functions in the main test.
        """
        # NOTE(sdague): try block is here because it's impossible to debug
        # where a failed data migration happens otherwise
        try:
            if with_data:
                data = None
                pre_upgrade = getattr(
                    self, "_pre_upgrade_%03d" % version, None)
                if pre_upgrade:
                    data = pre_upgrade(self.engine)

            self.migration_api.upgrade(self.engine, self.REPOSITORY, version)
            self.assertEqual(version,
                             self.migration_api.db_version(self.engine,
                                                           self.REPOSITORY))
            if with_data:
                check = getattr(self, "_check_%03d" % version, None)
                if check:
                    check(self.engine, data)
        except Exception:
            LOG.error(_LE("Failed to migrate to version %s on engine %s") %
                      (version, self.engine))
            raise
