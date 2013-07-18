# Copyright (c) 2013 Openstack Foundation.
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
"""Exposes an abstractbase decorator that works for both py2 and py3."""
import abc


def abstractbase(cls):
    """Converts an arbitrary class into an ABC. For example:
        @abstractbase
        class MetaX(object):
            @abc.abstractproperty
            def x(self):
                raise NotImplementedError()
            @abc.abstractmethod
            def morex(self):
                raise NotImplementedError()

        class X(MetaX):
            def __init__(self, x):
                self._x = x
            @property
            def x(self):
                return self._x
            def morex(self):
                self._x += 1

        a = X(1)  # fails with TypeError if either x or morex are missing
        assert type(a) is X
        assert issubclass(X, MetaX)
        assert isinstance(a, X)
        assert hasattr(X, 'register')

    :param cls: Class to convert into an ABC.
    """
    return abc.ABCMeta(cls.__name__, tuple(cls.mro()),
                       dict(cls.__dict__))
