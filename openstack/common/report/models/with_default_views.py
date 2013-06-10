from copy import copy
from openstack.common.models.base import ReportModel
import openstack.common.views.json.generic as jsonviews
import openstack.common.views.text.generic as textviews
import openstack.common.views.xml.generic as xmlviews


class ModelWithDefaultViews(ReportModel):
    def __init__(self, *args, **kwargs):
        self.views = {
            'text': textviews.KeyValueView(),
            'json': jsonviews.KeyValueView(),
            'xml': xmlviews.KeyValueView()
        }

        newargs = copy(kwargs)
        for k in kwargs:
            if k.endswith('_view'):
                self.views[k[0:-5]] = kwargs[k]
                del newargs[k]
        super(ModelWithDefaultViews, self).__init__(*args, **newargs)

    def set_current_view_type(self, tp):
        self.attached_view = self.views[tp]
        super(ModelWithDefaultViews, self).set_current_view_type(tp)

    def __getattr__(self, attrname):
        if attrname[0:3] == 'to_':
            if self.views[attrname[3:]] is not None:
                return self.views[attrname[3:]](self)
            else:
                raise NotImplementedError((
                    "Model {cn.__module__}.{cn.__name__} does not have" +
                    " a default view for {tp}").format(
                        cn=type(self), tp=attrname[3:]
                    )
                )
        else:
            return super(ModelWithDefaultViews, self).__getattr__(attrname)
