# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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
from oslo.config import cfg

CONF = cfg.CONF

MIGRATION_NAMESPACE = 'openstack.common.migration'


class MigrationManager(extension.ExtensionManager):

    @classmethod
    def initialize_oslo_parsers(cls, subparsers):
        _instance = cls(MIGRATION_NAMESPACE, invoke_on_load=True)

        up_parser = subparsers.add_parser('upgrade')
        up_parser.add_argument('revision', nargs='?', default=None)
        up_parser.set_defaults(func=_instance.upgrade)

        down_parser = subparsers.add_parser('downgrade')
        down_parser.add_argument('revision', nargs='?')
        down_parser.set_defaults(func=_instance.downgrade)

        version_parser = subparsers.add_parser('version')
        version_parser.set_defaults(func=_instance.version)

        revision_parser = subparsers.add_parser('revision')
        revision_parser.set_defaults(func=_instance.revision)
        revision_parser.add_argument('--message', type=str)
        revision_parser.add_argument('--autogenerate', action='store_true')

        stamp_parser = subparsers.add_parser('stamp')
        stamp_parser.set_defaults(func=_instance.stamp)
        stamp_parser.add_argument('revision')

    def _load_one_plugin(self, ep, invoke_on_load, invoke_args, invoke_kwds):
        plugin = ep.load()
        if plugin.check_available():
            return super(MigrationManager, self)._load_one_plugin(
                         ep, invoke_on_load, invoke_args, invoke_kwds)

    @property
    def plugins(self):
        """Returns plugins in sorted order
        """
        return sorted(ext.obj for ext in self.extensions)

    def upgrade(self):
        return [plugin.upgrade(CONF.command.revision)
                for plugin in self.plugins]

    def downgrade(self):
        #we need differntiate migrations based on criteria
        return [plugin.downgrade(CONF.command.revision)
                for plugin in reversed(self.plugins)]

    def version(self):
        last = None
        for plugin in self.plugins:
            version = plugin.obj.version()
            if version:
                last = version
        return last

    def revision(self):
        #revision should be done only by last plugin
        if not self.plugins:
            raise NotImplemented('There should be atleast one plugin active.')
        return self.plugins[-1].revision(
            CONF.command.message,
            CONF.command.autogenerate
        )

    def stamp(self):
        if not self.plugins:
            raise NotImplemented('There should be atleast one plugin active.')
        return self.plugins[-1].stamp(CONF.command.revision)
