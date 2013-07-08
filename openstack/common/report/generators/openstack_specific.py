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

"""Provides Openstack-specific generators

This module defines classes for Openstack-specific
generators for generating the models in
:mod:`openstack.common.report.models.openstack_specific`.
These generators are for use in the Guru Meditation
Reports.
"""

import greenlet
import openstack.common.report.models.openstack_specific as osm
from openstack.common.report.models import with_default_views as mwdv
import openstack.common.report.utils as rutils
from openstack.common.report.views.text.generic import MultiView
from oslo.config import cfg
import sys


class ThreadReportGenerator(object):
    """A Thread Data Generator

    This generator returns a collection of
    :class:`openstack.common.report.models.openstack_specific.ThreadModel`
    objects by introspecting the current python state using
    :func:`sys._current_frames()` .
    """

    def __call__(self):
        threadModels = [
            osm.ThreadModel(thread_id, stack)
            for thread_id, stack in sys._current_frames().items()
        ]

        thread_pairs = dict(zip(range(len(threadModels)), threadModels))
        return mwdv.ModelWithDefaultViews(thread_pairs,
                                          text_view=MultiView())


class GreenThreadReportGenerator(object):
    """A Green Thread Data Generator

    This generator returns a collection of
    :class:`openstack.common.report.models.openstack_specific.GreenThreadModel`
    objects by introspecting the current python garbage collection
    state, and sifting through for :class:`greenlet.greenlet` objects.

    .. seealso::

        Function :func:`openstack.common.report.utils._find_objects`
    """

    def __call__(self):
        threadModels = [
            osm.GreenThreadModel(gr.gr_frame)
            for gr in rutils._find_objects(greenlet.greenlet)
        ]

        thread_pairs = dict(zip(range(len(threadModels)), threadModels))
        return mwdv.ModelWithDefaultViews(thread_pairs,
                                          text_view=MultiView())


class ConfigReportGenerator(object):
    """A Configuration Data Generator

    This generator returns
    :class:`openstack.common.report.models.openstack_specific.ConfigModel` ,
    by default using the configuration options stored
    in :attr:`oslo.config.cfg.CONF`, which is where
    Openstack stores everything.

    :param cnf: the configuration option object
    :type cnf: :class:`oslo.config.cfg.ConfigOpts`
    """

    def __init__(self, cnf=cfg.CONF):
        self.conf_obj = cnf

    def __call__(self):
        return osm.ConfigModel(self.conf_obj)


class OldConfigReportGenerator(object):
    """A Configuration Data Generator

    This generator returns
    :class:`openstack.common.report.models.openstack_specific.ConfigModel` ,
    by default using the configuration options stored
    in :attr:`oslo.config.cfg.CONF`, which is where
    Openstack stores everything.

    :param cnf: the configuration option object
    :type cnf: :class:`oslo.config.cfg.ConfigOpts`
    """

    def __init__(self, cnf=cfg.CONF):
        self.conf_obj = cnf

    def __call__(self):
        return osm.OldConfigModel(self.conf_obj)


class PackageReportGenerator(object):
    """A Package Information Data Generator

    This generator returns
    :class:`openstack.common.report.models.openstack_specific.PackageModel`,
    extracting data from the given version object, which should follow
    the general format defined in Nova's version information (i.e. it
    should contain the methods vendor_string, product_string, and
    version_string_with_package).

    :param version_object: the version information object
    """

    def __init__(self, version_obj):
        self.version_obj = version_obj

    def __call__(self):
        return osm.PackageModel(
            self.version_obj.vendor_string(),
            self.version_obj.product_string(),
            self.version_obj.version_string_with_package()
        )
