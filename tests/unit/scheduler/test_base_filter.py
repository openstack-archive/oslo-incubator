# Copyright (c) 2013 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from openstack.common.scheduler import base_filter

from tests import utils


class TestBaseFilter(utils.BaseTestCase):

    def setUp(self):
        super(TestBaseFilter, self).setUp()
        self.filter = base_filter.BaseFilter()

    def test_filter_one_is_called(self):
        filters = [1, 2, 3, 4]
        filter_properties = {'x': 'y'}
        self.mox.StubOutWithMock(self.filter, '_filter_one')

        self.filter._filter_one(1, filter_properties).AndReturn(False)
        self.filter._filter_one(2, filter_properties).AndReturn(True)
        self.filter._filter_one(3, filter_properties).AndReturn(True)
        self.filter._filter_one(4, filter_properties).AndReturn(False)

        self.mox.ReplayAll()

        result = list(self.filter.filter_all(filters, filter_properties))
        self.assertEqual([2, 3], result)


class FakeExtension(object):

    def __init__(self, plugin):
        self.plugin = plugin


class BaseFakeFilter(base_filter.BaseFilter):
    pass


class FakeFilter1(BaseFakeFilter):
    """Derives from BaseFakeFilter and has a fake entry point defined.

    Entry point is returned by fake ExtensionManager.
    Should be included in the output of all_classes.
    """
    pass


class FakeFilter2(BaseFakeFilter):
    """Derives from BaseFakeFilter but has no entry point.

    Should be not included in all_classes.
    """
    pass


class FakeFilter3(base_filter.BaseFilter):
    """Does not derive from BaseFakeFilter.

    Should not be included.
    """
    pass


class FakeFilter4(BaseFakeFilter):
    """Derives from BaseFakeFilter and has an entry point.

    Should be included.
    """
    pass


class FakeFilter5(BaseFakeFilter):
    """Derives from BaseFakeFilter but has no entry point.

    Should not be included.
    """
    pass


class FakeExtensionManager(list):

    def __init__(self, namespace):
        classes = [FakeFilter1, FakeFilter3, FakeFilter4]
        exts = map(FakeExtension, classes)
        super(FakeExtensionManager, self).__init__(exts)
        self.namespace = namespace


class TestBaseFilterHandler(utils.BaseTestCase):

    def setUp(self):
        super(TestBaseFilterHandler, self).setUp()
        self.stubs.Set(base_filter.base_handler.extension, 'ExtensionManager',
                       FakeExtensionManager)
        self.handler = base_filter.BaseFilterHandler(BaseFakeFilter,
                                                     'fake_filters')

    def test_get_all_classes(self):
        # In order for a FakeFilter to be returned by get_all_classes, it has
        # to comply with these rules:
        # * It must be derived from BaseFakeFilter
        #   AND
        # * It must have a python entrypoint assigned (returned by
        #   FakeExtensionManager)
        expected = [FakeFilter1, FakeFilter4]
        result = self.handler.get_all_classes()
        self.assertEqual(expected, result)
