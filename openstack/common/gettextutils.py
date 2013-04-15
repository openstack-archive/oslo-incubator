# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
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
gettext for openstack-common modules.

Usual usage in an openstack.common module:

    from openstack.common.gettextutils import _
"""

import copy
import gettext
import inspect
import logging.handlers
import os
import re
import UserString

_localedir = os.environ.get('oslo'.upper() + '_LOCALEDIR')
_t = gettext.translation('oslo', localedir=_localedir, fallback=True)


def _(msg):
    return _t.ugettext(msg)


def install(domain):
    """Install a _() function using the given translation domain.

    Given a translation domain, install a _() function using gettext's
    install() function.

    The main difference from gettext.install() is that we allow
    overriding the default localedir (e.g. /usr/share/locale) using
    a translation-domain-specific environment variable (e.g.
    NOVA_LOCALEDIR).
    """
    gettext.install(domain,
                    localedir=os.environ.get(domain.upper() + '_LOCALEDIR'),
                    unicode=True)


"""
Lazy gettext functionality.

The following is an attempt to introduce a deferred way
to do translations on messages in OpenStack. We attempt to
override the standard _() function and % (format string) operation
to build Message objects that can later be translated when we have
more information. Also included is an example LogHandler that
translates Messages to an associated locale, effectively allowing
many logs, each with their own locale.
"""


def get_lazy_gettext(domain):
    """Assemble and return a lazy gettext function for a given domain.

    Factory method for a project/module to get a lazy gettext function
    for its own translation domain (i.e. nova, glance, cinder, etc.)
    """

    def _lazy_gettext(msg):
        """
        Create and return a Message object encapsulating a string
        so that we can translate it later when needed.
        """
        return Message(msg, domain)

    return _lazy_gettext


class Message(UserString.UserString, object):
    """Class used to encapsulate translatable messages."""
    def __init__(self, msg='', domain='oslo'):
        # _orig_str is the gettext msgid and should never change
        self._orig_str = msg
        self._left_extra_msg = ''
        self._right_extra_msg = ''
        self.params = None
        self.locale = None
        self.domain = domain

    @property
    def message(self):
        # NOTE(mrodden): this should always resolve to a string
        # that best represents the state of the message currently
        if self.locale:
            lang = gettext.translation(self.domain,
                                       languages=[self.locale],
                                       fallback=True)
        else:
            # use system locale for translations
            lang = gettext.translation(self.domain, fallback=True)

        full_msg = ''.join([self._left_extra_msg,
                            lang.ugettext(self._orig_str),
                            self._right_extra_msg])

        if self.params is not None:
            return full_msg % self.params
        else:
            return full_msg

    def _serialize_other(self, other):
        """
        Helper method that checks for python code-like objects
        and turns them into strings instead of trying to carry
        the full object around.
        """
        needs_str = [inspect.ismodule, inspect.isclass, inspect.ismethod,
                     inspect.isfunction, inspect.isgeneratorfunction,
                     inspect.isgenerator, inspect.istraceback,
                     inspect.isframe, inspect.iscode,
                     inspect.isbuiltin, inspect.isroutine,
                     inspect.isabstract, inspect.ismethoddescriptor,
                     inspect.isdatadescriptor, inspect.isgetsetdescriptor,
                     inspect.ismemberdescriptor]

        for atype in needs_str:
            if atype(other):
                return unicode(other)

        return None

    def _save_parameters(self, other):
        if isinstance(other, basestring):
            self.params = other
        elif isinstance(other, dict):
            full_msg = self.message
            # look for %(blah) fields in string;
            # ignore %% and deal with the
            # case where % is first character on the line
            keys = re.findall('(?:[^%]|^)%\((\w*)\)[a-z]', full_msg)

            # if we don't find any %(blah) blocks but have a %s
            if not keys and re.findall('(?:[^%]|^)%[a-z]', full_msg):
                # apparently the full dictionary is the parameter
                self.params = other
            else:
                self.params = {}
                for key in keys:
                    try:
                        self.params[key] = copy.deepcopy(other[key])
                    except Exception:
                        # cast uncopyable thing to string
                        self.params[key] = str(other[key])
        else:
            # attempt to cast nasty python object to string
            serialized_other = self._serialize_other(other)
            if serialized_other is not None:
                self.params = serialized_other
            else:
                copied = copy.copy(other)
                # we check for None later to see if
                # we actually have parameters to inject,
                # so encapsulate if our parameter is actually None
                if copied is None:
                    self.params = (copied, )
                else:
                    self.params = copied

        return self

    # overrides to be more string-like
    def __unicode__(self):
        return unicode(self.message)

    def __str__(self):
        return unicode(self.message).encode('utf-8')

    def __contains__(self, key):
        return key in self.message

    def __nonzero__(self):
        return bool(self.message)

    def __dir__(self):
        return dir(unicode)

    def __iter__(self):
        return iter(self.message)

    def __len__(self):
        return len(self.message)

    def __getattr__(self, name):
        if name == '__members__':
            return self.__dir__()
        return getattr(self.message, name)

    # not sure how much sense these next two methods make
    # to have around; hoping no one tries to use these seriously
    def __getitem__(self, key):
        return self.message[key]

    def __copy__(self):
        return self

    # operator overloads
    def __add__(self, other):
        self._right_extra_msg += other.__str__()
        return self

    def __radd__(self, other):
        self._left_extra_msg += other.__str__()
        return self

    def __mod__(self, other):
        # do a format string to catch and raise
        # any possible KeyErrors from missing parameters
        self.message % other
        return self._save_parameters(other)

    def __rmod__(self, other):
        return other % self.message

    def __mul__(self, other):
        return self.message * other

    def __rmul__(self, other):
        return other * self.message

    def __lt__(self, other):
        return self.message < other

    def __le__(self, other):
        return self.message <= other

    def __eq__(self, other):
        return self.message == other

    def __ne__(self, other):
        return self.message != other

    def __gt__(self, other):
        return self.message > other

    def __ge__(self, other):
        return self.message >= other


class LocaleHandler(logging.handlers.MemoryHandler):
    """Handler that can have a locale associated to translate Messages.

    A quick example of how to utilize the Message class above. We simply
    extend MemoryHandler because it is already set up to wrap other
    log handlers. Utilizing this, we simply add a locale attribute
    to translate LogRecord messages to when they come through the handler.
    """

    def __init__(self, *args, **kwargs):
        # grab locale and remove from kwargs, so
        # we don't accidentally confuse MemoryHandler
        self.locale = kwargs.pop('locale', None)
        logging.handlers.MemoryHandler.__init__(self, *args, **kwargs)

    def emit(self, record):
        if isinstance(record.msg, Message):
            # set the locale and resolve to a string
            record.msg.locale = self.locale
            record.msg = '%s' % record.msg

        logging.handlers.MemoryHandler.emit(self, record)
