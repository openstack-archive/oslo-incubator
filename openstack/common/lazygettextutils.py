# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 IBM Corp.
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
Lazy gettext functionality.

This module is an attempt to introduce a deferred way
to do translations on messages in OpenStack. We attempt to
override the standard _() function and % (format string) operation
to build Message objects that can later be translated when we have
more information. Also included is an example LogHandler that
translates Messages to an associated locale, effectively allowing
many logs, each with their own locale.
"""

import copy
import gettext
import inspect
import logging.handlers
import re


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


class Message(object):
    """Class used to encapsulate translatable messages."""
    def __init__(self, msg='', domain='oslo'):
        self.message = msg
        self.extra_msg = ''
        self.params = None
        self.locale = None
        self.domain = domain

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

    def __mod__(self, other):
        # do a format string to catch and raise
        # any possible KeyErrors from missing parameters
        (self.message + self.extra_msg) % other

        if isinstance(other, str):
            self.params = other
        elif isinstance(other, dict):
            full_msg = self.message + self.extra_msg
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

    def __add__(self, other):
        self.extra_msg += other.__str__()

    def __unicode__(self):
        """Behave like a string when needed

        Localize the message and inject parameters when
        we are requested to behave like a string (unicode) type
        """
        if self.locale:
            try:
                lang = gettext.translation(self.domain,
                                           languages=[self.locale])
                full_msg = lang.ugettext(self.message) + self.extra_msg
            except IOError:
                # no locale found so default to using no translation
                full_msg = self.message + self.extra_msg
        else:
            t = gettext.translation(self.domain, fallback=True)
            full_msg = t.ugettext(self.message) + self.extra_msg
        if self.params is not None:
            return unicode(full_msg % self.params)
        else:
            return unicode(full_msg)

    def __str__(self):
        """Behave like a string when needed

        Localize the message and inject parameters when
        we are requested to behave like a string (str) type
        """
        return unicode(self).encode('utf-8')

    def __contains__(self, item):
        return str(self).__contains__(item)

    def iteritems(self):
        # crude attempt at serialization
        local = dict(self.__dict__)
        return local.iteritems()

    def __getattr__(self, name):
        supported = ['find']
        if name in supported:
            return getattr(unicode(self), name)
        raise AttributeError()


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
