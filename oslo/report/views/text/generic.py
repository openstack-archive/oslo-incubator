from collections import Mapping
from collections import Sequence


class MultiView(object):

    def __call__(self, model):
        res = [str(model[key]) for key in model]
        return "\n".join(res)


class BasicKeyValueView(object):

    def __call__(self, model):
        res = ""
        for key in model:
            res += "{key} = {value}\n".format(key=key, value=model[key])

        return res


class KeyValueView(object):
    def __call__(self, model):
        def serialize(root, rootkey, indent):
            res = []
            if rootkey is not None:
                res.append(("  " * indent) + rootkey + " = ")

            if isinstance(root, Mapping):
                for key in root:
                    res.extend(serialize(root[key], key, indent + 1))
            elif (isinstance(root, Sequence) and
                    not isinstance(root, basestring)):
                for val in root:
                    res.extend(serialize(val, None, indent + 1))
            else:
                res[0] += str(root)

            return res

        return "\n".join(serialize(model, None, -1))


class TableView(object):
    def __init__(self, column_names, column_values, table_prop_name):
        self.table_prop_name = table_prop_name
        self.column_names = column_names
        self.column_values = column_values
        self.column_width = 72 / len(column_names) - len(column_names) + 1

        column_headers = "|".join(
            "{ch[" + str(n) + "]: ^" + str(self.column_width) + "}"
            for n in range(len(column_names))
            )

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
            res += self.row_fmt_str.format(cv=row) + "\n"

        return res
