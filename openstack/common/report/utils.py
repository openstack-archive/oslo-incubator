# Copyright 2013 Red Hat, Inc.
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

"""Various utilities for report generation

This module includes various utilities
used in generating reports.
"""

import collections as col
import copy
import gc


class StringWithAttrs(str):
    """A String that can have arbitrary attributes
    """

    pass


class SequenceToMappingProxy(col.Mapping):
    """A proxy from a sequence to a mapping using indicies as keys."""

    def __init__(self, underlying_seq):
        self.seq = underlying_seq

    def __getitem__(self, key):
        try:
            return self.seq[key]
        except TypeError:
            raise KeyError(key)

    def __len__(self):
        return len(self.seq)

    def __iter__(self):
        i = 0
        while i < len(self.seq):
            yield i
            i += 1

    def __repr__(self):
        return '<SequenceToMappingProxy %s>' % repr(self.seq)

    def __deepcopy__(self, memodict):
        return dict((k, copy.deepcopy(self[k], memodict)) for k in self)

    def __copy__(self):
        return SequenceToMappingProxy(self.seq)


class MutableSequenceToMappingProxy(SequenceToMappingProxy,
                                    col.MutableMapping):
    """A proxy from a mutable sequence to a mutable mapping."""
    def __setitem__(self, key, value):
        if not isinstance(key, int):
            raise TypeError(('list indicies must be integers, '
                             ' not %s') % type(key).__name__)

        self.seq[key] = value

    def __delitem__(self, key):
        if not isinstance(key, int):
            raise TypeError(('list indicies must be integers, '
                             ' not %s') % type(key).__name__)

        del self.seq[key]


class COWMapping(col.MutableMapping):
    """A Copy-On-Write mapping."""

    def __init__(self, underlying_mapping):
        self.old_data = underlying_mapping
        self.new_data = {}
        self.deleted_items = {}

    def __getitem__(self, key):
        try:
            return self.new_data[key]
        except KeyError:
            return self.old_data[key]

    def __setitem__(self, key, value):
        self.new_data[key] = value
        try:
            del self.deleted_items[key]
        except KeyError:
            pass

    def __delitem__(self, key):
        try:
            del self.new_data[key]
        except KeyError:
            if not self.old_data.has_item(key):
                raise KeyError(key)

            self.deleted_items[key] = 1

    def __len__(self):
        union_len = len(dict(self.old_items, **self.new_items))
        return union_len - len(self.deleted_items)

    def __iter__(self):
        for k in self.old_data.keys():
            if k in self.deleted_items:
                next
            yield k
        for k in self.new_data.keys():
            if k not in self.old_data:
                yield k

    def __repr__(self):
        res = '<COWMapping {'
        res += ', '.join(('%s: %s' % (k, v)) for k, v in self)
        res += '}>'
        return res

    def __copy__(self):
        res = COWMapping(self.old_data)
        res.new_data = self.new_data
        res.deleted_items = self.deleted_items
        return res

    def __deepcopy__(self, memodict):
        return dict(
            (copy.deepcopy(k, memodict), copy.deepcopy(self[k], memodict))
            for k, v in self.items())


def _find_objects(t):
    """Find Objects in the GC State

    This horribly hackish method locates objects of a
    given class in the current python instance's garbage
    collection state.  In case you couldn't tell, this is
    horribly hackish, but is necessary for locating all
    green threads, since they don't keep track of themselves
    like normal threads do in python.

    :param class t: the class of object to locate
    :rtype: list
    :returns: a list of objects of the given type
    """

    return [o for o in gc.get_objects() if isinstance(o, t)]
