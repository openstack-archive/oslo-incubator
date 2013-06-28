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

"""Greenthread local storage of variables using weak references"""

import threading
import weakref

try:
    import eventlet
    from eventlet import corolocal
    from eventlet import patcher
except ImportError:
    eventlet = None


class LocalStoreBuilder(object):
    """This object carries the logic to dynamically instantiate weak_local
       depending on the implementation. This helps our test cases by allowing
       us to specify which implementation to build on by passing in modules
       stored as variables.
    """

    def __init__(self, threading_mod, eventlet_mod=None):

        # NOTE(ldbragst): If eventlet_mod is passed in we can assume that it
        # it was imported properly and that we can set strong_store to
        # the corolocal.local implementation, and build weak_store
        # accordingly.
        if eventlet_mod:
            self.strong_store = corolocal.local
            self.weak_store = self._build_weak_store()
        else:
            # NOTE(ldbragst): Here we need to address the unit test concerns
            # by knowing that just because eventlet_mod = None doesn't mean
            # that it isn't installed on the system. So if it is installed,
            # grab the original threading implementation for the Python
            # standard library, using threading.local for strong_store and
            # build weak_store accordingly.
            if patcher.is_monkey_patched(threading_mod):
                threading_mod = patcher.original(threading_mod)
            self.strong_store = threading_mod.local
            self.weak_store = self._build_weak_store()

    def get_weak_store(self):
        """Return instance variable weak_store."""

        return self.weak_store

    def get_strong_store(self):
        """Return instance variable strong_store."""

        return self.strong_store

    def _build_weak_store(self):
        """Private method that builds a weak_store class dynamically depending
           on self.strong_store, which can either be Eventlet based or
           Python standard library threading.local.
        """

        def __getattribute__(self, attr):
            rval = self.strong_store.__getattribute__(self, attr)  # noqa
            if rval:
                # NOTE(mikal): this bit is confusing. What is stored is a weak
                # reference, not the value itself. We therefore need to lookup
                # the weak reference and return the inner value here.
                rval = rval()
            return rval

        def __setattr__(self, attr, value):
            value = weakref.ref(value)
            return self.strong_store.__setattr__(self, attr, value)  # noqa

        # NOTE(ldbragst): dynamically building weak_store accoring to
        # self.strong_store
        weak_store = type('WeakLocal', (self.strong_store,),
                          dict(strong_store=self.strong_store))
        weak_store.__getattribute__ = __getattribute__
        weak_store.__setattr__ = __setattr__
        return weak_store

builder = LocalStoreBuilder(threading, eventlet)
store = builder.get_weak_store()
weak_store = builder.get_weak_store()
strong_store = builder.get_strong_store()
