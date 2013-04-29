# Copyright 2010 Jacob Kaplan-Moss
# Copyright 2011 OpenStack LLC.
# Copyright 2012 Grid Dynamics.
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
Base utilities to build API operation managers and objects on top of.
"""
import urlparse

from openstack.common.apiclient import exceptions
from openstack.common.apiclient import utils


def monkey_patch():
    import sys
    for mod in ("glanceclient.common",
                "novaclient",
                "keystoneclient"):
        orig_mod = sys.modules.get("%s.base" % mod)
        if orig_mod is None:
            try:
                orig_mod = __import__(mod, {}, {}, ["base"]).base
            except ImportError:
                continue
        gl = globals()
        for attr in ("getid",
                     "Manager",
                     "ManagerWithFind",
                     "Resource"):
            setattr(orig_mod, attr, gl[attr])


# Python 2.4 compat
try:
    all
except NameError:
    def all(iterable):
        return True not in (not x for x in iterable)


def getid(obj):
    """
    Abstracts the common pattern of allowing both an object or an object's ID
    (UUID) as a parameter when dealing with relationships.
    """

    # Try to return the object's UUID first, if we have a UUID.
    try:
        if obj.uuid:
            return obj.uuid
    except AttributeError:
        pass
    try:
        return obj.id
    except AttributeError:
        return obj


class HookableMixin(object):
    """Mixin so classes can register and run hooks."""
    _hooks_map = {}

    @classmethod
    def add_hook(cls, hook_type, hook_func):
        if hook_type not in cls._hooks_map:
            cls._hooks_map[hook_type] = []

        cls._hooks_map[hook_type].append(hook_func)

    @classmethod
    def run_hooks(cls, hook_type, *args, **kwargs):
        hook_funcs = cls._hooks_map.get(hook_type) or []
        for hook_func in hook_funcs:
            hook_func(*args, **kwargs)


class Manager(HookableMixin):
    """
    Managers interact with a particular type of API (servers, flavors, images,
    etc.) and provide CRUD operations for them.
    """
    resource_class = None

    def __init__(self, api):
        self.api = api

    def _list(self, url, response_key, obj_class=None, body=None,
              iterate=None):
        if body:
            _resp, body = self.api.client.post(url, body=body)
        else:
            _resp, body = self.api.client.get(url)

        if obj_class is None:
            obj_class = self.resource_class

        data = body[response_key]
        # NOTE(ja): keystone returns values as list as {'values': [ ... ]}
        #           unlike other services which just return the list...
        if isinstance(data, dict):
            try:
                data = data['values']
            except KeyError:
                pass

        return [obj_class(self, res, loaded=True) for res in data if res]

    def _get(self, url, response_key):
        resp, body = self.api.get(url)
        return self.resource_class(self, body[response_key])

    def _create(self, url, body, response_key, return_raw=False):
        resp, body = self.api.post(url, body=body)
        if return_raw:
            return body[response_key]
        return self.resource_class(self, body[response_key])

    def _delete(self, url):
        resp, body = self.api.delete(url)

    def _update(self, url, body, response_key=None, method="PUT"):
        methods = {"PUT": self.api.put,
                   "POST": self.api.post}
        try:
            resp, body = methods[method](url, body=body)
        except KeyError:
            raise exceptions.ClientException("Invalid update method: %s"
                                             % method)
        # PUT requests may not return a body
        if body:
            if response_key is not None:
                return self.resource_class(self, body[response_key])
            else:
                return self.resource_class(self, body)


class ManagerWithFind(Manager):
    """
    Like a `Manager`, but with additional `find()`/`findall()` methods.
    """
    def find(self, **kwargs):
        """
        Find a single item with attributes matching ``**kwargs``.

        This isn't very efficient: it loads the entire list then filters on
        the Python side.
        """
        matches = self.findall(**kwargs)
        num_matches = len(matches)
        if num_matches == 0:
            msg = "No %s matching %s." % (self.resource_class.__name__, kwargs)
            raise exceptions.NotFound(404, msg)
        elif num_matches > 1:
            raise exceptions.NoUniqueMatch
        else:
            return matches[0]

    def findall(self, **kwargs):
        """
        Find all items with attributes matching ``**kwargs``.

        This isn't very efficient: it loads the entire list then filters on
        the Python side.
        """
        found = []
        searches = kwargs.items()

        for obj in self.list():
            try:
                if all(getattr(obj, attr) == value
                       for (attr, value) in searches):
                    found.append(obj)
            except AttributeError:
                continue

        return found


class Resource(object):
    """
    A resource represents a particular instance of an object (tenant, user,
    etc). This is pretty much just a bag for attributes.

    :param manager: Manager object
    :param info: dictionary representing resource attributes
    :param loaded: prevent lazy-loading if set to True
    """
    def __init__(self, manager, info, loaded=False):
        self.manager = manager
        self._info = info
        self._add_details(info)
        self._loaded = loaded

    def _add_details(self, info):
        for (k, v) in info.iteritems():
            try:
                setattr(self, k, v)
                self._info[k] = v
            except AttributeError:
                # In this case we already defined the attribute on the class
                pass

    def __getattr__(self, k):
        if k not in self.__dict__:
            #NOTE(bcwaldon): disallow lazy-loading if already loaded once
            if not self.is_loaded():
                self.get()
                return self.__getattr__(k)

            raise AttributeError(k)
        else:
            return self.__dict__[k]

    def __repr__(self):
        reprkeys = sorted(k for k in self.__dict__.keys() if k[0] != '_' and
                                                                k != 'manager')
        info = ", ".join("%s=%s" % (k, getattr(self, k)) for k in reprkeys)
        return "<%s %s>" % (self.__class__.__name__, info)

    def get(self):
        # set_loaded() first ... so if we have to bail, we know we tried.
        self.set_loaded(True)
        if not hasattr(self.manager, 'get'):
            return

        new = self.manager.get(self.id)
        if new:
            self._add_details(new._info)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if hasattr(self, 'id') and hasattr(other, 'id'):
            return self.id == other.id
        return self._info == other._info

    def is_loaded(self):
        return self._loaded

    def set_loaded(self, val):
        self._loaded = val


class Extension(HookableMixin):
    """Extension descriptor."""

    SUPPORTED_HOOKS = ('__pre_parse_args__', '__post_parse_args__')

    def __init__(self, name, module):
        self.name = name
        self.module = module
        self._parse_extension_module()

    def _parse_extension_module(self):
        self.manager_class = None
        for attr_name, attr_value in self.module.__dict__.items():
            if attr_name in self.SUPPORTED_HOOKS:
                self.add_hook(attr_name, attr_value)
            elif utils.safe_issubclass(attr_value, Manager):
                self.manager_class = attr_value

    def __repr__(self):
        return "<Extension '%s'>" % self.name
