from collections import Mapping
from copy import deepcopy


class ReportModel(Mapping):
    def __init__(self, data=None, attached_view=None):
        self.attached_view = attached_view
        if data is not None:
            self.data = data
        else:
            self.data = {}

    def __str__(self):
        self_cpy = deepcopy(self)
        for key in self_cpy:
            if getattr(self_cpy[key], 'attached_view', None) is not None:
                self_cpy[key] = str(self_cpy[key])

        if (self.attached_view is not None):
            return self.attached_view(self_cpy)
        else:
            return str(self_cpy)

    def __repr__(self):
        if self.attached_view is not None:
            return ("<Model {cl.__module__}.{cl.__name__} {dt}" +
                    " with view {vw.__module__}.{vw.__name__}>").format(
                        cl=type(self),
                        dt=self.data,
                        vw=type(self.attached_view)
                        )
        else:
            return ("<Model {cl.__module__}.{cl.__name__} {dt}" +
                    " with no view>").format(
                        cl=type(self),
                        dt=self.data
                        )

    def set_current_view_type(self, tp):
        for key in self:
            try:
                self[key].set_current_view_type(tp)
            except AttributeError:
                pass

    def __getitem__(self, attrname):
        return self.data[attrname]

    def __setitem__(self, attrname, attrval):
        self.data[attrname] = attrval

    def __contains__(self, key):
        return self.data.__contains__(key)

    def __getattr__(self, attrname):
        try:
            return self.data[attrname]
        except KeyError:
            raise AttributeError(
                "'{cl}' object has no attribute '{an}'".format(
                    cl=type(self).__name__, an=attrname
                    )
                )

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return self.data.__iter__()
