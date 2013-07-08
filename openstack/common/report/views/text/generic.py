# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

"""Provides generic text views

This modules provides several generic views for
serializing models into human-readable text.
"""

import collections as col


class MultiView(object):
    """A Text View Containing Multiple Views

    This view simply serializes each
    value in the data model, and then
    joins them with newlines (ignoring
    the key values altogether).  This is
    useful for serializing lists of models
    (as array-like dicts).
    """

    def __call__(self, model):
        res = [str(model[key]) for key in model]
        return "\n".join(res)


class BasicKeyValueView(object):
    """A Basic Key-Value Text View

    This view performs a naive serialization of a model into
    text using a basic key-value method, where each
    key-value pair is rendered as "key = str(value)"
    """

    def __call__(self, model):
        res = ""
        for key in model:
            res += "{key} = {value}\n".format(key=key, value=model[key])

        return res


class KeyValueView(object):
    """A Key-Value Text View

    This view performs an advanced serialization of a model
    into text by following the following set of rules:

    key : text
        key = text

    rootkey : Mapping
        ::

            rootkey =
              serialize(key, value)

    key : Sequence
        ::

            key =
              serialize(item)

    :param str indent_str: the string used to represent
                           one "indent"
    """

    def __init__(self, indent_str='  '):
        self.indent_str = indent_str

    def __call__(self, model):
        def serialize(root, rootkey, indent):
            res = []
            if rootkey is not None:
                res.append((self.indent_str * indent) + rootkey + " = ")

            if isinstance(root, col.Mapping):
                if rootkey is None and indent > 0:
                    res.append((self.indent_str * indent) + '[dict]')

                for key in root:
                    res.extend(serialize(root[key], key, indent + 1))
            elif (isinstance(root, col.Sequence) and
                    not isinstance(root, basestring)):
                for val in root:
                    res.extend(serialize(val, None, indent + 1))
            else:
                str_root = str(root)
                if '\n' in str_root:
                    list_root = [(self.indent_str * (indent + 1)) + line
                                 for line in str_root.split('\n')]
                    res.extend(list_root)
                else:
                    try:
                        res[0] += str_root
                    except IndexError:
                        res = [(self.indent_str * indent) + str_root]

            return res

        return "\n".join(serialize(model, None, -1))


class TableView(object):
    """A Basic Table Text View

    This view performs serialization of data into a basic table with
    predefined column names and mappings.  Column width is auto-calculated
    evenly, column values are automatically truncated accordingly.  Values
    are centered in the columns.

    :param [str] column_names: the headers for each of the columns
    :param [str] column_values: the item name to match each column to in
                                each row
    :param str table_prop_name: the name of the property within the model
                                containing the row models
    """

    def __init__(self, column_names, column_values, table_prop_name):
        self.table_prop_name = table_prop_name
        self.column_names = column_names
        self.column_values = column_values
        self.column_width = (72 - len(column_names) + 1) / len(column_names)

        column_headers = "|".join(
            "{ch[" + str(n) + "]: ^" + str(self.column_width) + "}"
            for n in range(len(column_names))
        )

        # correct for float-to-int roundoff error
        test_fmt = column_headers.format(ch=column_names)
        if len(test_fmt) < 72:
            column_headers += ' ' * (72 - len(test_fmt))

        vert_divider = '-' * 72
        self.header_fmt_str = column_headers + "\n" + vert_divider + "\n"

        self.row_fmt_str = "|".join(
            "{cv[" + str(n) + "]: ^" + str(self.column_width) + "}"
            for n in range(len(column_values))
        )

    def __call__(self, model):
        res = self.header_fmt_str.format(ch=self.column_names)
        for raw_row in model[self.table_prop_name]:
            row = [str(raw_row[prop_name]) for prop_name in self.column_values]
            # double format is in case we have roundoff error
            res += '{0: <72}\n'.format(self.row_fmt_str.format(cv=row))

        return res
