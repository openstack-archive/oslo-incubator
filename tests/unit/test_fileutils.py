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

import errno
import os
import shutil
import tempfile

import mox
from six import moves

from openstack.common import fileutils
from openstack.common import test


class EnsureTree(test.BaseTestCase):
    def test_ensure_tree(self):
        tmpdir = tempfile.mkdtemp()
        try:
            testdir = '%s/foo/bar/baz' % (tmpdir,)
            fileutils.ensure_tree(testdir)
            self.assertTrue(os.path.isdir(testdir))

        finally:
            if os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)


class TestCachedFile(test.BaseTestCase):

    def setUp(self):
        super(TestCachedFile, self).setUp()
        self.mox = mox.Mox()
        self.addCleanup(self.mox.UnsetStubs)

    def test_read_cached_file(self):
        self.mox.StubOutWithMock(os.path, "getmtime")
        os.path.getmtime(mox.IgnoreArg()).AndReturn(1)
        self.mox.ReplayAll()

        fileutils._FILE_CACHE = {
            '/this/is/a/fake': {"data": 1123, "mtime": 1}
        }
        fresh, data = fileutils.read_cached_file("/this/is/a/fake")
        fdata = fileutils._FILE_CACHE['/this/is/a/fake']["data"]
        self.assertEqual(fdata, data)

    def test_read_modified_cached_file(self):
        self.mox.StubOutWithMock(os.path, "getmtime")
        self.mox.StubOutWithMock(moves.builtins, 'open')
        os.path.getmtime(mox.IgnoreArg()).AndReturn(2)

        fake_contents = "lorem ipsum"
        fake_file = self.mox.CreateMockAnything()
        fake_file.read().AndReturn(fake_contents)
        fake_context_manager = self.mox.CreateMockAnything()
        fake_context_manager.__enter__().AndReturn(fake_file)
        fake_context_manager.__exit__(mox.IgnoreArg(),
                                      mox.IgnoreArg(),
                                      mox.IgnoreArg())

        moves.builtins.open(mox.IgnoreArg()).AndReturn(fake_context_manager)

        self.mox.ReplayAll()
        fileutils._FILE_CACHE = {
            '/this/is/a/fake': {"data": 1123, "mtime": 1}
        }

        fresh, data = fileutils.read_cached_file("/this/is/a/fake")
        self.assertEqual(data, fake_contents)
        self.assertTrue(fresh)


class DeleteIfExists(test.BaseTestCase):
    def test_file_present(self):
        tmpfile = tempfile.mktemp()

        open(tmpfile, 'w')
        fileutils.delete_if_exists(tmpfile)
        self.assertFalse(os.path.exists(tmpfile))

    def test_file_absent(self):
        tmpfile = tempfile.mktemp()

        fileutils.delete_if_exists(tmpfile)
        self.assertFalse(os.path.exists(tmpfile))

    def test_dir_present(self):
        tmpdir = tempfile.mktemp()
        os.mkdir(tmpdir)

        fileutils.delete_if_exists(tmpdir, remove=os.rmdir)
        self.assertFalse(os.path.exists(tmpdir))

    def test_file_error(self):
        def errm(path):
            raise OSError(errno.EINVAL, '')

        tmpfile = tempfile.mktemp()

        open(tmpfile, 'w')
        self.assertRaises(OSError, fileutils.delete_if_exists, tmpfile, errm)
        os.unlink(tmpfile)


class RemovePathOnError(test.BaseTestCase):
    def test_error(self):
        tmpfile = tempfile.mktemp()
        open(tmpfile, 'w')

        try:
            with fileutils.remove_path_on_error(tmpfile):
                raise Exception
        except Exception:
            self.assertFalse(os.path.exists(tmpfile))

    def test_no_error(self):
        tmpfile = tempfile.mktemp()
        open(tmpfile, 'w')

        with fileutils.remove_path_on_error(tmpfile):
            pass
        self.assertTrue(os.path.exists(tmpfile))
        os.unlink(tmpfile)

    def test_remove(self):
        tmpfile = tempfile.mktemp()
        open(tmpfile, 'w')

        try:
            with fileutils.remove_path_on_error(tmpfile, remove=lambda x: x):
                raise Exception
        except Exception:
            self.assertTrue(os.path.exists(tmpfile))
        os.unlink(tmpfile)

    def test_remove_dir(self):
        tmpdir = tempfile.mktemp()
        os.mkdir(tmpdir)

        try:
            with fileutils.remove_path_on_error(
                    tmpdir,
                    lambda path: fileutils.delete_if_exists(path, os.rmdir)):
                raise Exception
        except Exception:
            self.assertFalse(os.path.exists(tmpdir))


class UtilsTestCase(test.BaseTestCase):
    def test_file_open(self):
        dst_fd, dst_path = tempfile.mkstemp()
        try:
            os.close(dst_fd)
            with open(dst_path, 'w') as f:
                f.write('hello')
            with fileutils.file_open(dst_path, 'r') as fp:
                self.assertEqual(fp.read(), 'hello')
        finally:
            os.unlink(dst_path)


class WriteToTempfileTestCase(test.BaseTestCase):
    def setUp(self):
        super(WriteToTempfileTestCase, self).setUp()
        self.content = 'testing123'

    def check_file_content(self, path):
        with open(path, 'r') as fd:
            ans = fd.read()
            self.assertEqual(self.content, ans)

    def test_file_without_path_and_suffix(self):
        res = fileutils.write_to_tempfile(self.content)
        self.assertTrue(os.path.exists(res))

        (basepath, tmpfile) = os.path.split(res)
        self.assertTrue(basepath.startswith(tempfile.gettempdir()))
        self.assertTrue(tmpfile.startswith('tmp'))

        self.check_file_content(res)

    def test_file_with_not_existing_path(self):
        path = '/tmp/testing/test1'
        res = fileutils.write_to_tempfile(self.content, path=path)
        self.assertTrue(os.path.exists(res))
        (basepath, tmpfile) = os.path.split(res)
        self.assertEqual(basepath, path)
        self.assertTrue(tmpfile.startswith('tmp'))

        self.check_file_content(res)
        shutil.rmtree('/tmp/testing')

    def test_file_with_not_default_suffix(self):
        suffix = '.conf'
        res = fileutils.write_to_tempfile(self.content, suffix=suffix)
        self.assertTrue(os.path.exists(res))

        (basepath, tmpfile) = os.path.split(res)
        self.assertTrue(basepath.startswith(tempfile.gettempdir()))
        self.assertTrue(tmpfile.startswith('tmp'))
        self.assertTrue(tmpfile.endswith('.conf'))

        self.check_file_content(res)

    def test_file_with_not_existing_path_and_not_default_suffix(self):
        suffix = '.txt'
        path = '/tmp/testing/test2'
        res = fileutils.write_to_tempfile(self.content,
                                          path=path,
                                          suffix=suffix)
        self.assertTrue(os.path.exists(res))

        (basepath, tmpfile) = os.path.split(res)
        self.assertTrue(tmpfile.startswith('tmp'))
        self.assertEqual(basepath, path)
        self.assertTrue(tmpfile.endswith(suffix))

        self.check_file_content(res)
        shutil.rmtree('/tmp/testing')

    def test_file_with_not_default_prefix(self):
        prefix = 'test'
        res = fileutils.write_to_tempfile(self.content, prefix=prefix)
        self.assertTrue(os.path.exists(res))

        (basepath, tmpfile) = os.path.split(res)
        self.assertTrue(tmpfile.startswith(prefix))
        self.assertTrue(basepath.startswith(tempfile.gettempdir()))

        self.check_file_content(res)
