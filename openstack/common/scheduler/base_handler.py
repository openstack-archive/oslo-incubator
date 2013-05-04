# Copyright (c) 2011-2013 OpenStack Foundation.
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
"""
A common base for handling extension classes.

Used by BaseFilterHandler and BaseWeightHandler
"""

import inspect

from stevedore import extension


class BaseHandler(object):
    """ Base class to handle loading filter and weight classes.
    """
    def __init__(self, modifier_class_type, modifier_namespace):
        self.namespace = modifier_namespace
        self.modifier_class_type = modifier_class_type
        self.extension_manager = extension.ExtensionManager(modifier_namespace)

    def _is_correct_class(self, obj):
        """Return whether an object is a class of the correct type and
        is not prefixed with an underscore.
        """
        return (inspect.isclass(obj) and
                not obj.__name__.startswith('_') and
                issubclass(obj, self.modifier_class_type))

    def _do_get_all_classes(self, cls_list):
        for cls in cls_list:
            if inspect.isfunction(cls):
                # If it's a function, call it and recurse to get the
                # classes out of it
                for cls in self._do_get_all_classes(cls()):
                    yield cls
            elif self._is_correct_class(cls):
                yield cls

    def get_all_classes(self):
        # We use a set, as some classes may have an entrypoint of their own,
        # and also be returned by a function such as 'all_filters' for example
        return set(self._do_get_all_classes(
            [ext.plugin for ext in self.extension_manager]))
