# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
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

import logging

LOG = logging.getLogger(__name__)


def int_from_bool_as_string(subject):
    """
    Interpret a string as a boolean and return either 1 or 0.

    Any string value in:

        ('True', 'true', 'On', 'on', '1')

    is interpreted as a boolean True.

    Useful for JSON-decoded stuff and config file parsing
    """
    return bool_from_string(subject) and 1 or 0


def bool_from_string(subject):
    """
    Interpret a string as a boolean.

    Any string value in:

        ('True', 'true', 'On', 'on', 'Yes', 'yes', '1')

    is interpreted as a boolean True.

    Useful for JSON-decoded stuff and config file parsing
    """
    if isinstance(subject, bool):
        return subject
    if isinstance(subject, basestring):
        if subject.strip().lower() in ('true', 'on', 'yes', '1'):
            return True
    return False


def ensure_unicode(text, encoding='utf-8', errors='strict'):
    """
    Converts incoming objects to unicode and encodes
    them using `encoding`.

    :param encoding:    Expected encoding for text
    :param errors: Errors handling policy.
    :returns: text or a unicode `encoding` encoded
                representation of it.
    """
    if not isinstance(text, unicode):
        text = str(text).decode(encoding, errors)
    return text


def ensure_str(text, encoding='utf-8', errors='strict'):
    """
    Converts incoming objects to bytestring and encodes
    them using `encoding`.

    :param encoding:    Expected encoding for text
    :param errors: Errors handling policy.
    :returns: text or a bytestring `encoding` encoded
                representation of it.
    """

    if not isinstance(text, basestring):
        # try to convert `text` to string
        # This allows this method for receiving
        # objs that can be converted to string
        text = str(text)

    if isinstance(text, unicode):
        return text.encode(encoding, errors)
    elif text and encoding != 'utf-8':
        return text.decode('utf-8', errors).encode(encoding, errors)

    return text
