# Copyright (c) 2012 OpenStack Foundation
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

"""Decorator and config option definitions for adding custom code (hooks)
around callables.

Any method may have the 'add_hook' decorator applied, which yields the
ability to invoke Hook objects before or after the method. (i.e. pre and
post)

Hook objects are loaded by HookLoaders.  Each named hook may invoke multiple
Hooks.

Example Hook object:

class MyHook(object):
    def pre(self, *args, **kwargs):
        # do stuff before wrapped callable runs

    def post(self, rv, *args, **kwargs):
        # do stuff after wrapped callable runs

    def downgrade(self, *args, **kwargs):
        # do stuff to downgrade actions of this hook

Example Hook object with function parameters:

class MyHookWithFunction(object):
    def pre(self, f, *args, **kwargs):
        # do stuff with wrapped function info

    def post(self, f, *args, **kwards):
        # do stuff with wrapped function info

    def downgrade(self, *args, **kwargs):
        # do stuff to downgrade actions of this hook

"""

import functools

import stevedore

from openstack.common.gettextutils import _
from openstack.common import log as logging

LOG = logging.getLogger(__name__)
NS = 'openstack.common.hooks'
RB = 'ignore'

_HOOKS = {}  # hook name => hook manager


class HookMethodException(Exception):
    """Hook method raise Exception."""

    def __init__(self, exception, extension, method_type):
        message = (_('%(exc)s was caught while running %(type)s-hook '
                     'of %(name)s') % {'exc': exception, 'type': method_type,
                                       'name': extension})
        super(HookMethodException, self).__init__(message)


class HookManager(object):
    """Hook manager class for manipulating hooks.

    Coordinate execution of multiple extensions using a common name.
    """

    _ALLOWED_ROLLBACK_TYPES = ('ignore', 'full', 'local', 'raise')

    def __init__(self, name, rollback=RB):
        """Invoke_on_load creates an instance of the Hook class

        :param name: The name of the hooks to load.
        :type name: str
        :param rollback: This flag is responsible for rollback method.
            Can take values only from self._ALLOWED_ROLLBACK_TYPES.
            Raising AttributeError if the value does not match any element
            from self._ALLOWED_ROLLBACK_TYPES.
        :type rollback: str
        """
        self.api = stevedore.hook.HookManager(NS, name, invoke_on_load=True)

        if rollback not in self._ALLOWED_ROLLBACK_TYPES:
            msg = _('Wrong rollback type. Allowed types: %s') % \
                self._ALLOWED_ROLLBACK_TYPES
            raise AttributeError(msg)
        self.rollback = rollback

    @property
    def extensions(self):
        return self.api.extensions

    def downgrade(self, failed_extension, *args, **kwargs):
        failed_position = self.extensions.index(failed_extension) + 1
        extensions = self.extensions[:failed_position]
        extensions.reverse()
        for extension in extensions:
            obj = extension.obj
            downgrade_method = getattr(obj, 'downgrade', None)
            if downgrade_method:
                downgrade_method(*args, **kwargs)
            else:
                LOG.debug(_("%s doesn't have downgrade method.") % obj)

    def _run(self, name, method_type, args, kwargs, func):
        if method_type not in ('pre', 'post'):
            msg = _("Wrong type of hook method. "
                    "Only 'pre' and 'post' type allowed")
            raise ValueError(msg)

        for extension in self.api.extensions:
            obj = extension.obj
            hook_method = getattr(obj, method_type, None)
            if hook_method:
                msg = (_("Running %(name)s %(type)s-hook: %(obj)s") %
                       {'name': name, 'type': method_type, 'obj': obj})
                LOG.debug(msg)
                try:
                    if func:
                        hook_method(func, *args, **kwargs)
                    else:
                        hook_method(*args, **kwargs)
                except Exception as exc:
                    msg = (_('%(e)s error was caught during %(type)s-hook') %
                           {'e': exc, 'type': method_type})
                    LOG.exception(msg)

                    if self.rollback == 'full':
                        LOG.debug(_('Try to downgrade all executed hooks.'))

                        self.downgrade(extension, *args, **kwargs)
                        raise HookMethodException(extension=extension,
                                                  exception=exc,
                                                  method_type=method_type)
                    elif self.rollback == 'local':
                        LOG.debug(_('Try to rollback failed hook.'))

                        downgrade_method = getattr(obj, 'downgrade', None)
                        if downgrade_method:
                            downgrade_method(*args, **kwargs)
                        else:
                            LOG.debug(
                                _("%s doesn't have downgrade method.") % obj)
                    elif self.rollback == 'raise':
                        raise exc
                    elif self.rollback == 'ignore':
                        LOG.debug(_("%s will be ignored.") % exc)

    def run_pre(self, name, args, kwargs, f=None):
        """Execute optional pre methods of loaded hooks.

        :param name: The name of the loaded hooks.
        :param args: Positional arguments which would be transmitted into
                     all pre methods of loaded hooks.
        :param kwargs: Keyword args which would be transmitted into all pre
                       methods of loaded hooks.
        :param f: Target function.
        """
        self._run(name=name, method_type='pre', args=args, kwargs=kwargs,
                  func=f)

    def run_post(self, name, rv, args, kwargs, f=None):
        """Execute optional post methods of loaded hooks.

        :param name: The name of the loaded hooks.
        :param rv: Return values of target method call.
        :param args: Positional arguments which would be transmitted into
                     all post methods of loaded hooks.
        :param kwargs: Keyword args which would be transmitted into all post
                       methods of loaded hooks.
        :param f: Target function.
        """
        self._run(name=name, method_type='post', args=(rv,) + args,
                  kwargs=kwargs, func=f)


def add_hook(name, pass_function=False):
    """Execute optional pre and post methods around the decorated
    function.  This is useful for customization around callables.
    """
    def outer(f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            manager = get_hook(name)

            function = None
            if pass_function:
                function = f

            manager.run_pre(name, args, kwargs, f=function)
            rv = f(*args, **kwargs)
            manager.run_post(name, rv, args, kwargs, f=function)

            return rv

        return inner

    return outer


def get_hook(hook_name):
    """Return HookManager by name.

    Checks for the existence HookManager by given name.
    If there is no suitable HookManager, it will be created.
    Then the desired HookManager will be returned.
    """
    if hook_name not in _HOOKS:
        _HOOKS[hook_name] = HookManager(hook_name)

    return _HOOKS[hook_name]


def reset():
    """Clear loaded hooks."""
    _HOOKS.clear()
