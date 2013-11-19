# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
# Copyright 2013 IBM Corp.
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
import locale
import logging
import os
import re

from babel import localedata
import six

_localedir = os.environ.get('oslo'.upper() + '_LOCALEDIR')
_t = gettext.translation('oslo', localedir=_localedir, fallback=True)

_AVAILABLE_LANGUAGES = {}
USE_LAZY = False


def enable_lazy():
    """Convenience function for configuring _() to use lazy gettext

    Call this at the start of execution to enable the gettextutils._
    function to use lazy gettext functionality. This is useful if
    your project is importing _ directly instead of using the
    gettextutils.install() way of importing the _ function.
    """
    global USE_LAZY
    USE_LAZY = True


def _(msg):
    if USE_LAZY:
        return Message(msg, 'oslo')
    else:
        if six.PY3:
            return _t.gettext(msg)
        return _t.ugettext(msg)


def install(domain, lazy=False):
    """Install a _() function using the given translation domain.

    Given a translation domain, install a _() function using gettext's
    install() function.

    The main difference from gettext.install() is that we allow
    overriding the default localedir (e.g. /usr/share/locale) using
    a translation-domain-specific environment variable (e.g.
    NOVA_LOCALEDIR).

    :param domain: the translation domain
    :param lazy: indicates whether or not to install the lazy _() function.
                 The lazy _() introduces a way to do deferred translation
                 of messages by installing a _ that builds Message objects,
                 instead of strings, which can then be lazily translated into
                 any available locale.
    """
    if lazy:
        # NOTE(mrodden): Lazy gettext functionality.
        #
        # The following introduces a deferred way to do translations on
        # messages in OpenStack. We override the standard _() function
        # and % (format string) operation to build Message objects that can
        # later be translated when we have more information.
        #
        # Also included below is an example LocaleHandler that translates
        # Messages to an associated locale, effectively allowing many logs,
        # each with their own locale.

        def _lazy_gettext(msg):
            """Create and return a Message object.

            Lazy gettext function for a given domain, it is a factory method
            for a project/module to get a lazy gettext function for its own
            translation domain (i.e. nova, glance, cinder, etc.)

            Message encapsulates a string so that we can translate
            it later when needed.
            """
            return Message(msg, domain)

        from six import moves
        moves.builtins.__dict__['_'] = _lazy_gettext
    else:
        localedir = '%s_LOCALEDIR' % domain.upper()
        if six.PY3:
            gettext.install(domain,
                            localedir=os.environ.get(localedir))
        else:
            gettext.install(domain,
                            localedir=os.environ.get(localedir),
                            unicode=True)


class Message(unicode):
    """A Message object is a unicode object that can be translated.

    Translation of Message is done explicitly using the translate() method.
    For all non-translation intents and purposes, a Message is simply unicode,
    and can be treated as such.
    """

    def __new__(cls, msgid, domain='oslo', *args):
        # We want to initialize the parent unicode with the actual
        # object that would have been plain unicode otherwise
        msg = super(Message, cls).__new__(cls, msgid)
        msg.msgid = msgid
        msg.domain = domain
        msg.params = None
        msg._locale_dir = os.environ.get(msg.domain.upper() + '_LOCALEDIR')
        return msg

    def translate(self, desired_locale=None):
        """Translate this message to the desired locale.

        :param desired_locale: The desired locale to translate the message to,
                               if no locale is provided the message will be
                               translated to the system's default locale.

        :returns: the translated message in unicode
        """
        if not desired_locale:
            desired_locale = '.'.join(locale.getdefaultlocale())

        lang = gettext.translation(self.domain,
                                   localedir=self._locale_dir,
                                   languages=[desired_locale],
                                   fallback=True)
        if six.PY3:
            translator = lang.gettext
        else:
            translator = lang.ugettext

        translated_message = translator(self.msgid)

        if self.params is None:
            # No need for more translation
            return translated_message

        # This Message object may have been constructed with one or more
        # Message objects as substitution parameters, given as a single
        # Message or a tuple or Map containing various, so when translating
        # this Message we need to translate those Messages too.
        # We need to preserve the original params in case they do contain
        # Messages so that those message's IDs are preserved for future t9ns
        translated_params = copy.deepcopy(self.params)
        if isinstance(self.params, Message):
            translated_params = self.params.translate(desired_locale)
        elif isinstance(self.params, tuple):
            translated_params = tuple(param.translate(desired_locale)
                                      if isinstance(param, Message)
                                      else param for param in self.params)
        elif isinstance(self.params, dict):
            for param_key in self.params.keys():
                param = self.params[param_key]
                if isinstance(param, Message):
                    translated_param = param.translate(desired_locale)
                    translated_params[param_key] = translated_param

        translated_message = translated_message % translated_params

        return translated_message

    def __mod__(self, other):
        # When we mod a Message we want the actual operation to be performed
        # by the parent class (i.e. unicode()), the only thing  we do here is
        # save the original msgid and the parameters in case of a translation
        unicode_mod = super(Message, self).__mod__(other)
        modded = Message(unicode_mod, self.domain)
        modded.msgid = self.msgid
        modded.params = self._sanitize_mod_params(other)
        return modded

    def _sanitize_mod_params(self, other):
        """Sanitize the object being modded with this Message.

        - Add support for modding 'None' so translation supports it
        - Trim the modded object, which can be a large dictionary, to only
        those keys that would actually be used in a translation
        - Snapshot the object being modded, in case the message is
        translated, it will be used as it was when the Message was created
        """
        if other is None:
            params = (other,)
        elif isinstance(other, dict):
            params = self._trim_dictionary_parameters(other)
        else:
            params = self._copy(other)
        return params

    def _trim_dictionary_parameters(self, dict_param):
        """Return a dict that only has matching entries in the msgid."""
        # Look for %(blah) keys in msgid;
        # Skip %% and deal with the case where % is first character on the line
        keys = re.findall('(?:[^%]|^)?%\((\w*)\)[a-z]', self.msgid)

        # If we don't find any %(blah) keys but have a %s
        if not keys and re.findall('(?:[^%]|^)%[a-z]', self.msgid):
            # Apparently the full dictionary is the parameter
            params = copy.deepcopy(dict_param)
        else:
            params = {}
            for key in keys:
                params[key] = self._copy(dict_param[key])

        return params

    def _copy(self, source):
        try:
            return copy.deepcopy(source)
        except TypeError:
            # Fallback to casting to unicode this will handle the
            # python code-like objects that can't be deep-copied
            return six.text_type(source)

    def __repr__(self):
        return self.translate()


def get_available_languages(domain):
    """Lists the available languages for the given translation domain.

    :param domain: the domain to get languages for
    """
    if domain in _AVAILABLE_LANGUAGES:
        return copy.copy(_AVAILABLE_LANGUAGES[domain])

    localedir = '%s_LOCALEDIR' % domain.upper()
    find = lambda x: gettext.find(domain,
                                  localedir=os.environ.get(localedir),
                                  languages=[x])

    # NOTE(mrodden): en_US should always be available (and first in case
    # order matters) since our in-line message strings are en_US
    language_list = ['en_US']
    # NOTE(luisg): Babel <1.0 used a function called list(), which was
    # renamed to locale_identifiers() in >=1.0, the requirements master list
    # requires >=0.9.6, uncapped, so defensively work with both. We can remove
    # this check when the master list updates to >=1.0, and update all projects
    list_identifiers = (getattr(localedata, 'list', None) or
                        getattr(localedata, 'locale_identifiers'))
    locale_identifiers = list_identifiers()
    for i in locale_identifiers:
        if find(i) is not None:
            language_list.append(i)
    _AVAILABLE_LANGUAGES[domain] = language_list
    return copy.copy(language_list)


def get_localized_message(message, desired_locale=None):
    """Gets a localized version of the given message in the given locale.

    If the message is not a Message object the message is returned as-is.
    If the locale is None the message is translated to the default locale.

    This method is a convenience method so that translators don't always
    explicitly have to check if a string is a Message before translating it,
    but it also hides implementation details of the Message class.

    :param message: the message to translate, if the parameter is not a Message
                    the same parameter is returned as-is
    :param desired_locale: the locale to translate the message to, if None the
                           default system locale will be used
    :returns: the translated message in unicode, or the original message if
              it could not be translated
    """
    translated = message
    if isinstance(message, Message):
        translated = message.translate(desired_locale)
    return translated


class LocaleHandler(logging.Handler):
    """Handler that can have a locale associated to translate Messages.

    A quick example of how to utilize the Message class above.
    LocaleHandler takes a locale and a target logging.Handler object
    to forward LogRecord objects to after translating the internal Message.
    """

    def __init__(self, locale, target):
        """Initialize a LocaleHandler

        :param locale: locale to use for translating messages
        :param target: logging.Handler object to forward
                       LogRecord objects to after translation
        """
        logging.Handler.__init__(self)
        self.locale = locale
        self.target = target

    def emit(self, record):
        if isinstance(record.msg, Message):
            # set the locale and resolve to a string
            record.msg.locale = self.locale

        self.target.emit(record)
