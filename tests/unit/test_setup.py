# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
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
import sys
from tempfile import mkstemp
from tempfile import mkdtemp
import unittest
import shutil
import stubout

from openstack.common import setup as common_setup
from openstack.common.setup import *


class EmailTestCase(unittest.TestCase):

    def test_str_dict_replace(self):
        string = 'Johnnie T. Hozer'
        mapping = {'T.': 'The'}
        self.assertEqual('Johnnie The Hozer',
                         canonicalize_emails(string, mapping))


class MailmapTestCase(unittest.TestCase):

    def setUp(self):
        (fd, self.mailmap) = mkstemp(prefix='openstack', suffix='.setup')

    def tearDown(self):
        if os.path.exists(self.mailmap):
            os.remove(self.mailmap)

    def test_mailmap_with_fullname(self):
        with open(self.mailmap, 'w') as mm_fh:
            mm_fh.write("Foo Bar <email@foo.com> Foo Bar <email@bar.com>\n")
        self.assertEqual({'<email@bar.com>': '<email@foo.com>'},
                         parse_mailmap(self.mailmap))

    def test_mailmap_with_firstname(self):
        with open(self.mailmap, 'w') as mm_fh:
            mm_fh.write("Foo <email@foo.com> Foo <email@bar.com>\n")
        self.assertEqual({'<email@bar.com>': '<email@foo.com>'},
                         parse_mailmap(self.mailmap))

    def test_mailmap_with_noname(self):
        with open(self.mailmap, 'w') as mm_fh:
            mm_fh.write("<email@foo.com> <email@bar.com>\n")
        self.assertEqual({'<email@bar.com>': '<email@foo.com>'},
                         parse_mailmap(self.mailmap))


class FakePopen(object):
    fake_stdout = ""
    returncode = 0

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def communicate(self):
        return (self.fake_stdout, "")


class DiveToTmpDir():
    def __enter__(self):
        self.tmp_dir = mkdtemp(prefix='openstack', suffix='.setup-dir')
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp_dir)
        return self

    def __exit__(self, type, value, traceback):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp_dir)


class GitLogsTest(unittest.TestCase):

    def setUp(self):
        self.stubs = stubout.StubOutForTesting()

    def tearDown(self):
        self.stubs.UnsetAll()

    def test_write_git_changelog(self):
        FakePopen.fake_stdout = "Author: Foo Bar <email@bar.com>\n"

        self.stubs.Set(os.path, "isdir",
                       lambda path: True)
        self.stubs.Set(subprocess, "Popen",
                       FakePopen)

        with DiveToTmpDir():
            with open(".mailmap", 'w') as mm_fh:
                mm_fh.write("Foo Bar <email@foo.com> <email@bar.com>\n")

            write_git_changelog()
            with open("ChangeLog", 'r') as ch_fh:
                self.assertTrue("email@foo.com" in ch_fh.read())

    def test_generate_authors(self):
        author_old = "Foo Foo <email@foo.com>"
        author_new = "Bar Bar <email@bar.com>"

        def fake_run_shell_command(cmd):
            if cmd.startswith("git log"):
                return author_new
            return None

        self.stubs.Set(os.path, "isdir",
                       lambda path: True)
        self.stubs.Set(common_setup, "_run_shell_command",
                       fake_run_shell_command)

        with DiveToTmpDir():
            with open("AUTHORS.in", 'w') as auth_fh:
                auth_fh.write(author_old)
            generate_authors()
            with open("AUTHORS", 'r') as auth_fh:
                authors = auth_fh.read()
                self.assertTrue(author_old in authors)
                self.assertTrue(author_new in authors)


class GetCmdClassTest(unittest.TestCase):

    def setUp(self):
        self.stubs = stubout.StubOutForTesting()

    def tearDown(self):
        self.stubs.UnsetAll()

    def test_get_cmdclass(self):
        cmdclass = get_cmdclass()

        self.assertTrue('sdist' in cmdclass)
        build_sphinx = cmdclass.get('build_sphinx')
        if build_sphinx:
            from distutils.dist import Distribution
            from sphinx.setup_command import BuildDoc
            self.stubs.Set(BuildDoc, "run", lambda self: None)
            distr = Distribution()
            distr.packages = ("fake_package",)
            distr.command_options["build_sphinx"] = {"source_dir": ["a", "."]}

            build_doc = build_sphinx(distr)

            with DiveToTmpDir():
                os.mkdir("fake_package")
                with open("fake_package/__init__.py", "w"):
                    pass
                with open("fake_package/fake_module.py", "w"):
                    pass

                build_doc.run()

                self.assertTrue(
                    os.path.exists("api/autoindex.rst"))
                self.assertTrue(
                    os.path.exists("api/fake_package.fake_module.rst"))


class ParseRequirementsTest(unittest.TestCase):

    def setUp(self):
        (fd, self.tmp_file) = mkstemp(prefix='openstack', suffix='.setup')

    def tearDown(self):
        if os.path.exists(self.tmp_file):
            os.remove(self.tmp_file)

    def test_parse_requirements_normal(self):
        with open(self.tmp_file, 'w') as fh:
            fh.write("foo\nbar")
        self.assertEqual(['foo', 'bar'],
                         parse_requirements([self.tmp_file]))

    def test_parse_requirements_with_git_egg_url(self):
        with open(self.tmp_file, 'w') as fh:
            fh.write("-e git://foo.com/zipball#egg=bar")
        self.assertEqual(['bar'], parse_requirements([self.tmp_file]))

    def test_parse_requirements_with_http_egg_url(self):
        with open(self.tmp_file, 'w') as fh:
            fh.write("https://foo.com/zipball#egg=bar")
        self.assertEqual(['bar'], parse_requirements([self.tmp_file]))

    def test_parse_requirements_removes_index_lines(self):
        with open(self.tmp_file, 'w') as fh:
            fh.write("-f foobar")
        self.assertEqual([], parse_requirements([self.tmp_file]))

    def test_parse_requirements_removes_argparse(self):
        with open(self.tmp_file, 'w') as fh:
            fh.write("argparse")
        if sys.version_info >= (2, 7):
            self.assertEqual([], parse_requirements([self.tmp_file]))

    def test_get_requirement_from_file_empty(self):
        actual = get_reqs_from_files([])
        self.assertEqual([], actual)


class ParseDependencyLinksTest(unittest.TestCase):

    def setUp(self):
        (fd, self.tmp_file) = mkstemp(prefix='openstack', suffix='.setup')

    def tearDown(self):
        if os.path.exists(self.tmp_file):
            os.remove(self.tmp_file)

    def test_parse_dependency_normal(self):
        with open(self.tmp_file, 'w') as fh:
            fh.write("http://test.com\n")
        self.assertEqual(
            ['http://test.com'],
            parse_dependency_links([self.tmp_file]))

    def test_parse_dependency_with_git_egg_url(self):
        with open(self.tmp_file, 'w') as fh:
            fh.write("-e git://foo.com/zipball#egg=bar")
        self.assertEqual(
            ['git://foo.com/zipball#egg=bar'],
            parse_dependency_links([self.tmp_file]))
