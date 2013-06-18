# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import distutils.version as dist_version
import os

from openstack.common.db.sqlalchemy import session as db_session
from openstack.common import exception


import migrate
from migrate.versioning import util as migrate_util
import sqlalchemy


@migrate_util.decorator
def patched_with_engine(f, *a, **kw):
    url = a[0]
    engine = migrate_util.construct_engine(url, **kw)

    try:
        kw['engine'] = engine
        return f(*a, **kw)
    finally:
        if isinstance(engine, migrate_util.Engine) and engine is not url:
            migrate_util.log.debug('Disposing SQLAlchemy engine %s', engine)
            engine.dispose()


# TODO(jkoelker) When migrate 0.7.3 is released and nova depends
#                on that version or higher, this can be removed
MIN_PKG_VERSION = dist_version.StrictVersion('0.7.3')
if (not hasattr(migrate, '__version__') or
        dist_version.StrictVersion(migrate.__version__) < MIN_PKG_VERSION):
    migrate_util.with_engine = patched_with_engine


# NOTE(jkoelker) Delay importing migrate until we are patched
from migrate import exceptions as versioning_exceptions
from migrate.versioning import api as versioning_api
from migrate.versioning.repository import Repository

_REPOSITORY = None

get_engine = db_session.get_engine


def db_sync(abs_path, version=None):
    if version is not None:
        try:
            version = int(version)
        except ValueError:
            raise exception.OpenstackException(
                _("version should be an integer"))

    current_version = db_version(abs_path)
    repository = _find_migrate_repo(abs_path)
    if version is None or version > current_version:
        return versioning_api.upgrade(get_engine(), repository, version)
    else:
        return versioning_api.downgrade(get_engine(), repository,
                                        version)


def db_version(abs_path, init_version):
    repository = _find_migrate_repo(abs_path)
    try:
        return versioning_api.db_version(get_engine(), repository)
    except versioning_exceptions.DatabaseNotControlledError:
        meta = sqlalchemy.MetaData()
        engine = get_engine()
        meta.reflect(bind=engine)
        tables = meta.tables
        if len(tables) == 0:
            db_version_control(abs_path, init_version)
            return versioning_api.db_version(get_engine(), repository)
        else:
            # Some pre-Essex DB's may not be version controlled.
            # Require them to upgrade using Essex first.
            raise exception.OpenstackException(
                _("Upgrade DB using Essex release first."))


def db_version_control(abs_path, version=None):
    repository = _find_migrate_repo(abs_path)
    versioning_api.version_control(get_engine(), repository, version)
    return version


def _find_migrate_repo(abs_path):
    """Get the path for the migrate repository."""
    global _REPOSITORY
    path = os.path.join(abs_path, "sqlalchemy", "migrate_repo")
    assert os.path.exists(path)
    if _REPOSITORY is None:
        _REPOSITORY = Repository(path)
    return _REPOSITORY
