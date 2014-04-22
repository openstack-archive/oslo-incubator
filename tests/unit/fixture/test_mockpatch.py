# Copyright 2014 IBM Corp.
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


##############################################################################
##############################################################################
##
## DO NOT MODIFY THIS FILE
##
## This file is being graduated to the oslotest library. Please make all
## changes there, and only backport critical fixes here. - dhellmann
##
##############################################################################
##############################################################################


from six.moves import mock

from openstack.common.fixture import mockpatch
from tests import utils


class Foo(object):
    def bar(self):
        pass


def mocking_bar(self):
    return 'mocked!'


class TestMockPatch(utils.BaseTestCase):
    def test_mock_patch_with_replacement(self):
        self.useFixture(mockpatch.Patch('%s.Foo.bar' % (__name__),
                                        mocking_bar))
        instance = Foo()
        self.assertEqual(instance.bar(), 'mocked!')

    def test_mock_patch_without_replacement(self):
        self.useFixture(mockpatch.Patch('%s.Foo.bar' % (__name__)))
        instance = Foo()
        self.assertIsInstance(instance.bar(), mock.MagicMock)


class TestMockPatchObject(utils.BaseTestCase):
    def test_mock_patch_object_with_replacement(self):
        self.useFixture(mockpatch.PatchObject(Foo, 'bar', mocking_bar))
        instance = Foo()
        self.assertEqual(instance.bar(), 'mocked!')

    def test_mock_patch_object_without_replacement(self):
        self.useFixture(mockpatch.PatchObject(Foo, 'bar'))
        instance = Foo()
        self.assertIsInstance(instance.bar(), mock.MagicMock)
