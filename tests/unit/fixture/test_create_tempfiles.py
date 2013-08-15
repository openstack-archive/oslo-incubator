# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 Mirantis, Inc.
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

from openstack.common.fixture import create_tempfiles
from tests.utils import BaseTestCase


class CreateTempfilesTestCase(BaseTestCase):
    def setUp(self):
        super(CreateTempfilesTestCase, self).setUp()
        tempfiles_fixture = self.useFixture(create_tempfiles.CreateTempfiles())
        self.create_tempfiles = tempfiles_fixture.create_tempfiles

    def test_files_with_abs_path(self):
        files = [('/tmp/test1', 'testing123'),
                 ('/tmp/test2', 'testing567')]
        res = self.create_tempfiles(files)
        self.assertTrue(os.path.exists(res[0]))
        self.assertTrue(os.path.exists(res[1]))

        self.assertEquals(res[0], files[0][0] + '.conf')
        self.assertEquals(res[1], files[1][0] + '.conf')

        for num in xrange(2):
            fd = open(res[num], 'r')
            ans = fd.read()
            self.assertEquals(files[num][1], ans)
            fd.close()

    def test_files_without_abs_path(self):
        files = [('test3', 'testing123'),
                 ('test4', 'testing567')]
        res = self.create_tempfiles(files)
        self.assertTrue(os.path.exists(res[0]))
        self.assertTrue(os.path.exists(res[1]))

        # equal left part of path
        path1 = res[0].rsplit('/', 1)
        path2 = res[1].rsplit('/', 1)
        self.assertEquals(path1[0], path2[0])
        self.assertNotEquals(path1[1], path2[1])

        # check right part of path
        self.assertTrue(path1[1].startswith(files[0][0]))
        self.assertTrue(path2[1].startswith(files[1][0]))

        self.assertTrue(path1[1].endswith('.conf'))
        self.assertTrue(path2[1].endswith('.conf'))

        for num in xrange(2):
            fd = open(res[num], 'r')
            ans = fd.read()
            self.assertEquals(files[num][1], ans)
            fd.close()

    def test_files_with_other_extension(self):
        files = [('test5', 'testing123')]
        res = self.create_tempfiles(files, ext='.txt')
        self.assertTrue(os.path.exists(res[0]))

        fd = open(res[0], 'r')
        ans = fd.read()
        self.assertEquals(files[0][1], ans)
        fd.close()
