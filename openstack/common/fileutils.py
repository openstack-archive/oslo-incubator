# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack Foundation.
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


import contextlib
import errno
import os
import tempfile

from openstack.common import excutils
from openstack.common.gettextutils import _  # noqa
from openstack.common import log as logging

LOG = logging.getLogger(__name__)

_FILE_CACHE = {}


def ensure_tree(path):
    """Create a directory (and any ancestor directories required)

    :param path: Directory to create
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            if not os.path.isdir(path):
                raise
        else:
            raise


def read_cached_file(filename, force_reload=False):
    """Read from a file if it has been modified.

    :param force_reload: Whether to reload the file.
    :returns: A tuple with a boolean specifying if the data is fresh
              or not.
    """
    global _FILE_CACHE

    if force_reload and filename in _FILE_CACHE:
        del _FILE_CACHE[filename]

    reloaded = False
    mtime = os.path.getmtime(filename)
    cache_info = _FILE_CACHE.setdefault(filename, {})

    if not cache_info or mtime > cache_info.get('mtime', 0):
        LOG.debug(_("Reloading cached file %s") % filename)
        with open(filename) as fap:
            cache_info['data'] = fap.read()
        cache_info['mtime'] = mtime
        reloaded = True
    return (reloaded, cache_info['data'])


def delete_if_exists(path):
    """Delete a file, but ignore file not found error.

    :param path: File to delete
    """

    try:
        os.unlink(path)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return
        else:
            raise


@contextlib.contextmanager
def remove_path_on_error(path):
    """Protect code that wants to operate on PATH atomically.
    Any exception will cause PATH to be removed.

    :param path: File to work with
    """
    try:
        yield
    except Exception:
        with excutils.save_and_reraise_exception():
            delete_if_exists(path)


def file_open(*args, **kwargs):
    """Open file

    see built-in file() documentation for more details

    Note: The reason this is kept in a separate module is to easily
    be able to provide a stub module that doesn't alter system
    state at all (for unit tests)
    """
    return file(*args, **kwargs)


def create_tempfile(content, path='', suffix=''):
    """Create temporary file or use existed file.

    This util is needed for creating tempfile with
    specified content and extension. If path are existed,
    it will be used for wriring content.

    For example: it can be used in database tests for creating
    configuration files.
    """
    if not os.path.isabs(path):
        (fd, path) = tempfile.mkstemp(suffix=suffix)
    else:
        fd = os.open(path, os.O_CREAT | os.O_WRONLY)
    try:
        os.write(fd, content)
    finally:
        os.close(fd)
    return path


def create_tempfiles(files):
    """Create some temporary files or use existed files.

    This util is needed for creating some tempfiles with
    specified content and extension.

    :param files: list of dictionaries with description file.
                  File has following attribute:
                  path - absolute path by existing file with
                         extension.
                  content - information for writing in file.
                  suffix - suffix for tempfile.
    """
    tempfiles = []
    params = {}
    for current_file in files:
        for val in ('path', 'suffix', 'content'):
            if val in current_file:
                params[val] = current_file[val]
            else:
                params[val] = ''

        path = create_tempfile(path=params['path'],
                               suffix=params['suffix'],
                               content=params['content'])
        tempfiles.append(path)
    return tempfiles
