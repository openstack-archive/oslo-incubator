# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import itertools


def first(seq, default=None, key=None):
    '''A simple idiomatic function inspired by: https://github.com/hynek/first.

    return the first item in the iterator matching key() or default.
    This little function simply aims to improve readablity.

    :param seq: an iterator
    :param default: result if nothing found
    :param key: a selection function
    '''
    if key is None:
        key = bool
    return next(itertools.ifilter(key, seq), default)