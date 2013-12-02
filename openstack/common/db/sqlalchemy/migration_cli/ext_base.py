# Copyright 2013 Mirantis Inc.
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

import abc
import six


@six.add_metaclass(abc.ABCMeta)
class MigrationExtensionBase(object):

    #used to sort migration in logical order
    order = 0

    @classmethod
    def check_available(cls):
        """Used for availability verification of a plugin.

        :rtype: bool
        """
        return False

    @abc.abstractmethod
    def upgrade(self, version):
        pass

    @abc.abstractmethod
    def downgrade(self, version):
        pass

    @abc.abstractmethod
    def version(self):
        pass

    def revision(self, *args, **kwargs):
        raise NotImplementedError()

    def stamp(self, *args, **kwargs):
        raise NotImplementedError()

    def __cmp__(self, other):
        return self.order > other.order
