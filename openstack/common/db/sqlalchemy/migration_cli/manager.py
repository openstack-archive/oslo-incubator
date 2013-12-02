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

from stevedore import extension


MIGRATION_NAMESPACE = 'openstack.common.migration'


class MigrationManager(extension.ExtensionManager):

    def _load_one_plugin(self, ep, invoke_on_load, invoke_args, invoke_kwds):
        """Initialize plugin only if it passes availability check."""
        plugin = ep.load()
        if plugin.check_available():
            return super(MigrationManager, self)._load_one_plugin(
                ep, invoke_on_load, invoke_args, invoke_kwds)

    @property
    def plugins(self):
        """Returns plugins in sorted order."""
        return sorted(ext.obj for ext in self.extensions)

    def upgrade(self, revision):
        """Upgrade database with all available backends."""
        results = []
        for plugin in self.plugins:
            results.append(plugin.upgrade(revision))
        return results

    def downgrade(self, revision):
        """Downgrade database with available backends."""
        #downgrading should be performed in reversed order
        results = []
        for plugin in reversed(self.plugins):
            results.append(plugin.downgrade(revision))
        return results

    def version(self):
        """Return last version of db."""
        last = None
        for plugin in self.plugins:
            version = plugin.version()
            if version:
                last = version
        return last

    def revision(self, message, autogenerate):
        """Generate template or autogenerated revision."""
        #revision should be done only by last plugin
        if not self.plugins:
            raise ValueError('There must be at least one plugin active.')
        return self.plugins[-1].revision(message, autogenerate)

    def stamp(self, revision):
        """Create stamp for a given revision."""
        if not self.plugins:
            raise ValueError('There must be at least one plugin active.')
        return self.plugins[-1].stamp(revision)
