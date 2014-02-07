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

from alembic import autogenerate as autogen
from alembic import config as alembic_config
from alembic import environment
import alembic.migration as alembic_migration
from alembic import script
from alembic import util

from openstack.common.db.sqlalchemy.migration_cli import ext_base


class AlembicExtension(ext_base.MigrationExtensionBase):

    order = 2

    @property
    def enabled(self):
        return os.path.exists(self.alembic_ini_path)

    def __init__(self, engine, migration_config):
        """Extension to provide alembic features.

        :param migration_config: Stores specific configuration for migrations
        :type migration_config: dict
        """
        self.engine = engine
        self.alembic_ini_path = migration_config.get('alembic_ini_path', '')
        self.config = alembic_config.Config(self.alembic_ini_path)
        # option should be used if script is not in default directory
        repo_path = migration_config.get('alembic_repo_path')
        if repo_path:
            self.config.set_main_option('script_location', repo_path)

        self.config.set_main_option('sqlalchemy.url', str(self.engine.url))

    def upgrade(self, revision, sql=False, tag=None):
        # if no revision provided upgrade to head
        revision = revision or 'head'
        script_dir = script.ScriptDirectory.from_config(self.config)

        starting_rev = None
        if ":" in revision:
            if not sql:
                raise util.CommandError("Range revision not allowed")
            starting_rev, revision = revision.split(':', 2)

        def upgrade(rev, context):
            return script_dir._upgrade_revs(revision, rev)

        with self.engine.connect() as conn:
            with environment.EnvironmentContext(
                self.config,
                script_dir,
                fn=upgrade,
                as_sql=sql,
                starting_rev=starting_rev,
                destination_rev=revision,
                tag=tag,
            ) as env:
                env.configure(connection=conn)
                script_dir.run_env()

    def downgrade(self, revision, sql=False, tag=None):
        # integer is used for revisions in sqlalchemy-migrate
        # so if one provided - just downgrade to alembic base state
        if isinstance(revision, int) or revision is None or revision.isdigit():
            revision = 'base'
        script_dir = script.ScriptDirectory.from_config(self.config)
        starting_rev = None
        if ":" in revision:
            if not sql:
                raise util.CommandError("Range revision not allowed")
            starting_rev, revision = revision.split(':', 2)
        elif sql:
            raise util.CommandError("downgrade with --sql"
                                    "requires <fromrev>:<torev>")

        def downgrade(rev, context):
            return script_dir._downgrade_revs(revision, rev)

        with self.engine.connect() as conn:
            with environment.EnvironmentContext(
                self.config,
                script_dir,
                fn=downgrade,
                as_sql=sql,
                starting_rev=starting_rev,
                destination_rev=revision,
                tag=tag,
            ) as env:
                env.configure(connection=conn)
                script_dir.run_env()

    def version(self):
        with self.engine.connect() as conn:
            context = alembic_migration.MigrationContext.configure(conn)
            return context.get_current_revision()

    def revision(self, message=None, autogenerate=False, sql=False,
                 update_template_args=None):
        """Creates template for migration.

        :param message: Text that will be used for migration title
        :type message: string
        :param autogenerate: If True - generates diff based on current database
                             state
        :type autogenerate: bool
        :param sql: If True run offline migration mode
        :type sql: bool
        :param update_template_args: Used to update template_args dict
        """
        script_dir = script.ScriptDirectory.from_config(self.config)
        template_args = {
            'config': self.config  # Let templates use config for
                                   # e.g. multiple databases
        }

        if update_template_args:
            template_args.update(update_template_args)

        imports = set()

        environ = util.asbool(
            self.config.get_main_option("revision_environment")
        )

        if autogenerate:
            environ = True

            def retrieve_migrations(rev, context):
                if (script_dir.get_revision(rev)
                        is not script_dir.get_revision("head")):
                    raise util.CommandError("Target database is"
                                            "not up to date.")
                autogen._produce_migration_diffs(
                    context, template_args, imports)
                return []
        elif environ:
            def retrieve_migrations(rev, context):
                return []

        with self.engine.connect() as conn:
            if environ:
                with environment.EnvironmentContext(
                    self.config,
                    script_dir,
                    fn=retrieve_migrations,
                    as_sql=sql,
                    template_args=template_args,
                ) as env:
                    env.configure(connection=conn)
                    script_dir.run_env()
            script_dir.generate_revision(util.rev_id(), message,
                                         **template_args)

    def stamp(self, revision, sql=False, tag=None):
        """Stamps database with provided revision.

        :param revision: Should match one from repository or head - to stamp
                         database with most recent revision
        :type revision: string
        """
        script_dir = script.ScriptDirectory.from_config(self.config)

        def do_stamp(rev, context):
            if sql:
                current = False
            else:
                current = context._current_rev()
            dest = script_dir.get_revision(revision)
            if dest is not None:
                dest = dest.revision
            context._update_current_rev(current, dest)
            return []

        with self.engine.connect() as conn:
            with environment.EnvironmentContext(
                self.config,
                script_dir,
                fn=do_stamp,
                as_sql=sql,
                destination_rev=revision,
                tag=tag,
            ) as env:
                env.configure(connection=conn)
                script_dir.run_env()
