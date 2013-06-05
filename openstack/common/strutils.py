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

"""
System-level utilities and helper functions.
"""

import sys

from openstack.common.gettextutils import _


# Used for looking up extensions of text
# to their 'multiplied' byte amount
BYTE_MULTIPLIERS = {
    '': 1,
    't': 1024 ** 4,
    'g': 1024 ** 3,
    'm': 1024 ** 2,
    'k': 1024,
}


TRUE_STRINGS = ('1', 't', 'true', 'on', 'y', 'yes')
FALSE_STRINGS = ('0', 'f', 'false', 'off', 'n', 'no')


def int_from_bool_as_string(subject):
    """
    Interpret a string as a boolean and return either 1 or 0.

    Any string value in:

        ('True', 'true', 'On', 'on', '1')

    is interpreted as a boolean True.

    Useful for JSON-decoded stuff and config file parsing
    """
    return bool_from_string(subject) and 1 or 0


def bool_from_string(subject, strict=False):
    """
    Interpret a string as a boolean.

    A case-insensitive match is performed such that strings matching 't',
    'true', 'on', 'y', 'yes', or '1' are considered True and, when
    `strict=False`, anything else is considered False.

    Useful for JSON-decoded stuff and config file parsing.

    If `strict=True`, unrecognized values, including None, will raise a
    ValueError which is useful when parsing values passed in from an API call.
    Strings yielding False are 'f', 'false', 'off', 'n', 'no', or '0'.
    """
    if not isinstance(subject, basestring):
        subject = str(subject)

    lowered = subject.strip().lower()

    if lowered in TRUE_STRINGS:
        return True
    elif lowered in FALSE_STRINGS:
        return False
    elif strict:
        acceptable = ', '.join(
            "'%s'" % s for s in sorted(TRUE_STRINGS + FALSE_STRINGS))
        msg = _("Unrecognized value '%(val)s', acceptable values are:"
                " %(acceptable)s") % {'val': subject,
                                      'acceptable': acceptable}
        raise ValueError(msg)
    else:
        return False


def safe_decode(text, incoming=None, errors='strict'):
    """
    Decodes incoming str using `incoming` if they're
    not already unicode.

    :param incoming: Text's current encoding
    :param errors: Errors handling policy. See here for valid
        values http://docs.python.org/2/library/codecs.html
    :returns: text or a unicode `incoming` encoded
                representation of it.
    :raises TypeError: If text is not an isntance of basestring
    """
    if not isinstance(text, basestring):
        raise TypeError("%s can't be decoded" % type(text))

    if isinstance(text, unicode):
        return text

    if not incoming:
        incoming = (sys.stdin.encoding or
                    sys.getdefaultencoding())

    try:
        return text.decode(incoming, errors)
    except UnicodeDecodeError:
        # Note(flaper87) If we get here, it means that
        # sys.stdin.encoding / sys.getdefaultencoding
        # didn't return a suitable encoding to decode
        # text. This happens mostly when global LANG
        # var is not set correctly and there's no
        # default encoding. In this case, most likely
        # python will use ASCII or ANSI encoders as
        # default encodings but they won't be capable
        # of decoding non-ASCII characters.
        #
        # Also, UTF-8 is being used since it's an ASCII
        # extension.
        return text.decode('utf-8', errors)


def safe_encode(text, incoming=None,
                encoding='utf-8', errors='strict'):
    """
    Encodes incoming str/unicode using `encoding`. If
    incoming is not specified, text is expected to
    be encoded with current python's default encoding.
    (`sys.getdefaultencoding`)

    :param incoming: Text's current encoding
    :param encoding: Expected encoding for text (Default UTF-8)
    :param errors: Errors handling policy. See here for valid
        values http://docs.python.org/2/library/codecs.html
    :returns: text or a bytestring `encoding` encoded
                representation of it.
    :raises TypeError: If text is not an isntance of basestring
    """
    if not isinstance(text, basestring):
        raise TypeError("%s can't be encoded" % type(text))

    if not incoming:
        incoming = (sys.stdin.encoding or
                    sys.getdefaultencoding())

    if isinstance(text, unicode):
        return text.encode(encoding, errors)
    elif text and encoding != incoming:
        # Decode text before encoding it with `encoding`
        text = safe_decode(text, incoming, errors)
        return text.encode(encoding, errors)

    return text


def to_bytes(text, default=0):
    """Try to turn a string into a number of bytes. Looks at the last
    characters of the text to determine what conversion is needed to
    turn the input text into a byte number.

    Supports: B/b, K/k, M/m, G/g, T/t (or the same with b/B on the end)

    """
    # Take off everything not number 'like' (which should leave
    # only the byte 'identifier' left)
    mult_key_org = text.lstrip('-1234567890')
    mult_key = mult_key_org.lower()
    mult_key_len = len(mult_key)
    if mult_key.endswith("b"):
        mult_key = mult_key[0:-1]
    try:
        multiplier = BYTE_MULTIPLIERS[mult_key]
        if mult_key_len:
            # Empty cases shouldn't cause text[0:-0]
            text = text[0:-mult_key_len]
        return int(text) * multiplier
    except KeyError:
        msg = _('Unknown byte multiplier: %s') % mult_key_org
        raise TypeError(msg)
    except ValueError:
        return default
