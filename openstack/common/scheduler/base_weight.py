# Copyright (c) 2011-2012 OpenStack Foundation.
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
Pluggable Weighing support
"""

import abc

import six

from openstack.common.scheduler import base_handler


def normalize(weight_list, minval=None, maxval=None):
    """Normalize the values in a list between 0 and 1.0.

    The normalization is made regarding the lower and upper values present in
    weight_list. If the minval and/or maxval parameters are set, these values
    will be used instead of the minimum and maximum from the list.

    If all the values are equal, they are normalized to 0.
    """

    if not weight_list:
        return ()

    if maxval is None:
        maxval = max(weight_list)

    if minval is None:
        minval = min(weight_list)

    maxval = float(maxval)
    minval = float(minval)

    if minval == maxval:
        return [0] * len(weight_list)

    range_ = maxval - minval
    return ((i - minval) / range_ for i in weight_list)


class WeighedObject(object):
    """Object with weight information."""
    def __init__(self, obj, weight):
        self.obj = obj
        self.weight = weight

    def __repr__(self):
        return "<WeighedObject '%s': %s>" % (self.obj, self.weight)


@six.add_metaclass(abc.ABCMeta)
class BaseWeigher(object):
    """Base class for pluggable weighers.

    The attributes maxval and minval can be specified to set up the maximum
    and minimum values for the weighed objects. These values will then be
    taken into account in the normalization step, instead of taking the values
    from the calculated weights.
    """

    minval = None
    maxval = None

    def weight_multiplier(self):
        """How weighted this weigher should be.

        Override this method in a subclass, so that the returned value is
        read from a configuration option to permit operators specify a
        multiplier for the weigher.
        """
        return 1.0

    @abc.abstractmethod
    def _weigh_object(self, obj, weight_properties):
        """Override in a subclass to specify a weight for a specific
        object.
        """

    def weigh_objects(self, weighed_obj_list, weight_properties):
        """Weigh multiple objects.

        Override in a subclass if you need access to all objects in order
        to calculate weights. Do not modify the weight of an object here,
        just return a list of weights.
        """
        # Calculate the weights
        weights = []
        for obj in weighed_obj_list:
            weight = self._weigh_object(obj.obj, weight_properties)

            # Record the min and max values if they are None. If they anything
            # but none we assume that the weigher has set them
            if self.minval is None:
                self.minval = weight
            if self.maxval is None:
                self.maxval = weight

            if weight < self.minval:
                self.minval = weight
            elif weight > self.maxval:
                self.maxval = weight

            weights.append(weight)

        return weights


class BaseWeightHandler(base_handler.BaseHandler):
    object_class = WeighedObject

    def get_weighed_objects(self, weigher_classes, obj_list,
                            weighing_properties):
        """Return a sorted (descending), normalized list of WeighedObjects."""

        if not obj_list:
            return []

        weighed_objs = [self.object_class(obj, 0.0) for obj in obj_list]
        for weigher_cls in weigher_classes:
            weigher = weigher_cls()
            weights = weigher.weigh_objects(weighed_objs, weighing_properties)

            # Normalize the weights
            weights = normalize(weights,
                                minval=weigher.minval,
                                maxval=weigher.maxval)

            for i, weight in enumerate(weights):
                obj = weighed_objs[i]
                obj.weight += weigher.weight_multiplier() * weight

        return sorted(weighed_objs, key=lambda x: x.weight, reverse=True)
