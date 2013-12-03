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
import logging.handlers
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
        return Message(msg, domain='oslo')
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
        def _lazy_gettext(msg):
            """Create and return a Message object.

            Lazy gettext function for a given domain, it is a factory method
            for a project/module to get a lazy gettext function for its own
            translation domain (i.e. nova, glance, cinder, etc.)

            Message encapsulates a string so that we can translate
            it later when needed.
            """
            return Message(msg, domain=domain)

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


class Message(six.text_type):
    """A Message object is a unicode object that can be translated.

    Translation of Message is done explicitly using the translate() method.
    For all non-translation intents and purposes, a Message is simply unicode,
    and can be treated as such.
    """

    def __new__(cls, base, msgid=None, params=None, domain='oslo', *args):
        """Create a new Message object.

        In order for translation to work gettext requires a message ID.
        If no explicit msgid is given, the base unicode given will be used as
        the message ID.
        """
        # We want to initialize the parent unicode with the actual
        # object that would have been plain unicode otherwise
        msg = super(Message, cls).__new__(cls, base)
        msg.msgid = msgid or base
        msg.domain = domain
        msg.params = params
        return msg

    def translate(self, desired_locale=None):
        """Translate this message to the desired locale.

        :param desired_locale: The desired locale to translate the message to,
                               if no locale is provided the message will be
                               translated to the system's default locale.

        :returns: the translated message in unicode
        """
        if not desired_locale:
            system_locale = locale.getdefaultlocale()
            # If the system locale is not available to the runtime use English
            if not system_locale[0]:
                desired_locale = 'en_US'
            else:
                desired_locale = system_locale[0]

        locale_dir = os.environ.get(self.domain.upper() + '_LOCALEDIR')
        lang = gettext.translation(self.domain,
                                   localedir=locale_dir,
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

        # This Message object may have been formatted with one or more
        # Message objects as substitution parameters, given either as a single
        # parameter, part of a tuple, or as one or more values in a dictionary.
        # When translating this Message we need to translate those Messages too
        if isinstance(self.params, tuple):
            translated_params = tuple(translate(param, desired_locale)
                                      for param in self.params)
        elif isinstance(self.params, dict):
            translated_params = {}
            for (param_key, param_value) in self.params.iteritems():
                translated_param = translate(param_value, desired_locale)
                translated_params[param_key] = translated_param
        else:
            translated_params = translate(self.params, desired_locale)

        translated_message = translated_message % translated_params

        return translated_message

    def __mod__(self, other):
        # When we mod a Message we want the actual operation to be performed
        # by the parent class (i.e. unicode()), the only thing  we do here is
        # save the original msgid and the parameters in case of a translation
        unicode_mod = super(Message, self).__mod__(other)
        modded = Message(unicode_mod,
                         msgid=self.msgid,
                         params=self._sanitize_mod_params(other),
                         domain=self.domain)
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
            params = self._copy_param(other)
        return params

    def _trim_dictionary_parameters(self, dict_param):
        """Return a dict that only has matching entries in the msgid."""
        # NOTE(luisg): Here we trim down the dictionary passed as parameters
        # to avoid carrying a lot of unnecessary weight around in the message
        # object, for example if someone passes in Message() % locals() but
        # only some params are used, and additionally we prevent errors for
        # non-deepcopyable objects by unicoding() them.

        # Look for %(param) keys in msgid;
        # Skip %% and deal with the case where % is first character on the line
        keys = re.findall('(?:[^%]|^)?%\((\w*)\)[a-z]', self.msgid)

        # If we don't find any %(param) keys but have a %s
        if not keys and re.findall('(?:[^%]|^)%[a-z]', self.msgid):
            # Apparently the full dictionary is the parameter
            params = self._copy_param(dict_param)
        else:
            params = {}
            for key in keys:
                params[key] = self._copy_param(dict_param[key])

        return params

    def _copy_param(self, param):
        try:
            return copy.deepcopy(param)
        except TypeError:
            # Fallback to casting to unicode this will handle the
            # python code-like objects that can't be deep-copied
            return six.text_type(param)

    def __add__(self, other):
        msg = _('Message objects do not support addition.')
        raise TypeError(msg)

    def __radd__(self, other):
        return self.__add__(other)

    def __str__(self):
        # NOTE(luisg): Logging in python 2.6 tries to str() log records,
        # and it expects specifically a UnicodeError in order to proceed.
        msg = _('Message objects do not support str() because they may '
                'contain non-ascii characters. '
                'Please use unicode() or translate() instead.')
        raise UnicodeError(msg)


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


def translate(obj, desired_locale=None):
    """Gets the translated unicode representation of the given object.

    If the object is not translatable it is returned as-is.
    If the locale is None the object is translated to the system locale.

    :param obj: the object to translate
    :param desired_locale: the locale to translate the message to, if None the
                           default system locale will be used
    :returns: the translated object in unicode, or the original object if
              it could not be translated
    """
    message = obj
    if not isinstance(message, Message):
        # If the object to translate is not already translatable,
        # let's first get its unicode representation
        message = six.text_type(obj)
    if isinstance(message, Message):
        # Even after unicoding() we still need to check if we are
        # running with translatable unicode before translating
        return message.translate(desired_locale)
    return obj


class TranslationHandler(logging.handlers.MemoryHandler):
    """Handler that translates records before logging them.

    The TranslationHandler takes a locale and a target logging.Handler object
    to forward LogRecord objects to after translating them. This handler
    depends on Message objects being logged, instead of regular strings.

    The handler can be configured declaratively in the logging.conf as follows:

        [handlers]
        keys = translatedlog, translator

        [handler_translatedlog]
        class = handlers.WatchedFileHandler
        args = ('/var/log/api-localized.log',)
        formatter = context

        [handler_translator]
        class = openstack.common.log.TranslationHandler
        target = tarnslatedlog
        args = ('zh_CN',)

    If the specified locale is not available in the system, the handler will
    log in the default locale.
    """

    def __init__(self, locale=None, target=None):
        """Initialize a TranslationHandler

        :param locale: locale to use for translating messages
        :param target: logging.Handler object to forward
                       LogRecord objects to after translation
        """
        # NOTE(luisg): In order to allow this handler to be a wrapper for
        # other handlers, such as a FileHandler, and still be able to
        # configure it using logging.conf, this handler has to extend
        # MemoryHandler because only the MemoryHandlers' logging.conf
        # parsing is implemented such that it accepts a target handler.
        logging.handlers.MemoryHandler.__init__(self,
                                                capacity=0,
                                                target=target)
        self.locale = locale

    def set_locale(self, locale):
        """Sets the locale for this handler."""
        self.locale = locale

    def setFormatter(self, fmt):
        self.target.setFormatter(fmt)

    def emit(self, record):
        # We save the message from the original record to restore it
        # after translation, so other handlers are not affected by this
        original_msg = record.msg
        original_args = record.args

        try:
            self._translate_and_log_record(record)
        finally:
            record.msg = original_msg
            record.args = original_args

    def _translate_and_log_record(self, record):
        record.msg = translate(record.msg, self.locale)
        # In addition to translating the message, we also need to translate
        # arguments that were passed to the log method that were not part
        # of the main message e.g., log.info(_('Some message %s'), this_one))
        if isinstance(record.args, tuple):
            record.args = tuple(translate(arg, self.locale)
                                for arg in record.args)
        if isinstance(record.args, dict):
            args_dict = {}
            for (arg_key, arg_value) in record.args.iteritems():
                translated_arg = translate(arg_value, self.locale)
                args_dict[arg_key] = translated_arg
            record.args = args_dict

        self.target.emit(record)
