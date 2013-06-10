import greenlet
from oslo.config import cfg
import oslo.report.models.openstack as osm
from oslo.report.models.with_default_views import ModelWithDefaultViews as MWDV
import oslo.report.utils as rutils
from oslo.report.views.text.generic import MultiView
import sys


class ThreadReportGenerator(object):
    def __call__(self):
        threadModels = [
            osm.ThreadModel(thread_id, stack)
            for thread_id, stack in sys._current_frames().items()
            ]
        return MWDV(
            dict(zip(range(len(threadModels)), threadModels)),
            text_view=MultiView()
            )


class GreenThreadReportGenerator(object):
    def __call__(self):
        threadModels = [
            osm.GreenThreadModel(gr.gr_frame)
            for gr in rutils._find_objects(greenlet.greenlet)
            ]

        return MWDV(
            dict(zip(range(len(threadModels)), threadModels)),
            text_view=MultiView()
            )


class ConfigReportGenerator(object):
    def __init__(self, cnf=cfg.CONF):
        self.conf_obj = cnf

    def __call__(self):
        return osm.ConfigModel(self.conf_obj)


class PackageReportGenerator(object):
    def __init__(self, version_obj):
        self.version_obj = version_obj

    def __call__(self):
        return osm.PackageModel(
            self.version_obj.vendor_string(),
            self.version_obj.product_string(),
            self.version_obj.version_string_with_package()
            )
