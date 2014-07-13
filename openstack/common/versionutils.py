# Copyright (c) 2013 OpenStack Foundation
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
Helpers for comparing version strings.
"""

import functools

import pkg_resources

from openstack.common.gettextutils import _
from openstack.common import log as logging


LOG = logging.getLogger(__name__)


class deprecated(object):
    """A decorator to mark callables as deprecated.

    This decorator logs a deprecation message when the callable it decorates is
    used. The message will include the release where the callable was
    deprecated, the release where it may be removed and possibly an optional
    replacement.

    Examples:

    1. Specifying the required deprecated release

    >>> @deprecated(as_of=deprecated.ICEHOUSE)
    ... def a(): pass

    2. Specifying a replacement:

    >>> @deprecated(as_of=deprecated.ICEHOUSE, in_favor_of='f()')
    ... def b(): pass

    3. Specifying the release where the functionality may be removed:

    >>> @deprecated(as_of=deprecated.ICEHOUSE, remove_in=+1)
    ... def c(): pass

    4. Specifying the deprecated functionality will not be removed:
    >>> @deprecated(as_of=deprecated.ICEHOUSE, remove_in=0)
    ... def d(): pass

    5. Specifying a replacement, deprecated functionality will not be removed:
    >>> @deprecated(as_of=deprecated.ICEHOUSE, in_favor_of='f()', remove_in=0)
    ... def e(): pass

    """

    # NOTE(morganfainberg): Bexar is used for unit test purposes, it is
    # expected we maintain a gap between Bexar and Folsom in this list.
    BEXAR = 'B'
    FOLSOM = 'F'
    GRIZZLY = 'G'
    HAVANA = 'H'
    ICEHOUSE = 'I'
    JUNO = 'J'

    _RELEASES = {
        # NOTE(morganfainberg): Bexar is used for unit test purposes, it is
        # expected we maintain a gap between Bexar and Folsom in this list.
        'B': 'Bexar',
        'F': 'Folsom',
        'G': 'Grizzly',
        'H': 'Havana',
        'I': 'Icehouse',
        'J': 'Juno',
    }

    _deprecated_msg_with_alternative = _(
        '%(what)s is deprecated as of %(as_of)s in favor of '
        '%(in_favor_of)s and may be removed in %(remove_in)s.')

    _deprecated_msg_no_alternative = _(
        '%(what)s is deprecated as of %(as_of)s and may be '
        'removed in %(remove_in)s. It will not be superseded.')

    _deprecated_msg_with_alternative_no_removal = _(
        '%(what)s is deprecated as of %(as_of)s in favor of %(in_favor_of)s.')

    _deprecated_msg_with_no_alternative_no_removal = _(
        '%(what)s is deprecated as of %(as_of)s. It will not be superseded.')

    def __init__(self, as_of, in_favor_of=None, remove_in=2, what=None):
        """Initialize decorator

        :param as_of: the release deprecating the callable. Constants
            are define in this class for convenience.
        :param in_favor_of: the replacement for the callable (optional)
        :param remove_in: an integer specifying how many releases to wait
            before removing (default: 2)
        :param what: name of the thing being deprecated (default: the
            callable's name)

        """
        self.as_of = as_of
        self.in_favor_of = in_favor_of
        self.remove_in = remove_in
        self.what = what

    def __call__(self, func):
        if not self.what:
            self.what = func.__name__ + '()'

        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            msg, details = self._build_message()
            LOG.deprecated(msg, details)
            return func(*args, **kwargs)
        return wrapped

    def _get_safe_to_remove_release(self, release):
        # TODO(dstanek): this method will have to be reimplemented once
        #    when we get to the X release because once we get to the Y
        #    release, what is Y+2?
        new_release = chr(ord(release) + self.remove_in)
        if new_release in self._RELEASES:
            return self._RELEASES[new_release]
        else:
            return new_release

    def _build_message(self):
        details = dict(what=self.what,
                       as_of=self._RELEASES[self.as_of],
                       remove_in=self._get_safe_to_remove_release(self.as_of))

        if self.in_favor_of:
            details['in_favor_of'] = self.in_favor_of
            if self.remove_in > 0:
                msg = self._deprecated_msg_with_alternative
            else:
                # There are no plans to remove this function, but it is
                # now deprecated.
                msg = self._deprecated_msg_with_alternative_no_removal
        else:
            if self.remove_in > 0:
                msg = self._deprecated_msg_no_alternative
            else:
                # There are no plans to remove this function, but it is
                # now deprecated.
                msg = self._deprecated_msg_with_no_alternative_no_removal
        return msg, details


def is_compatible(requested_version, current_version, same_major=True):
    """Determine whether `requested_version` is satisfied by
    `current_version`; in other words, `current_version` is >=
    `requested_version`.

    :param requested_version: version to check for compatibility
    :param current_version: version to check against
    :param same_major: if True, the major version must be identical between
        `requested_version` and `current_version`. This is used when a
        major-version difference indicates incompatibility between the two
        versions. Since this is the common-case in practice, the default is
        True.
    :returns: True if compatible, False if not
    """
    requested_parts = pkg_resources.parse_version(requested_version)
    current_parts = pkg_resources.parse_version(current_version)

    if same_major and (requested_parts[0] != current_parts[0]):
        return False

    return current_parts >= requested_parts
