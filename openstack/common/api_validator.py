# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 NEC Corporation.  All rights reserved.
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
# @author: Ken'ichi Ohmichi

import jsonschema

from openstack.common import uuidutils


def validated_type(f):
    class __inner(object):
        def __instancecheck__(self, instance):
            return f(instance)
    return __inner()


@validated_type
def validate_string_integer(instance):
    try:
        #NOTE(oomichi): To support a string integer such as "10", use
        #               int(instance) instead of isinstance(instance, int).
        int(instance)
    except ValueError:
        return False
    else:
        return True


types = {
    'integer': validate_string_integer,
    'uuid': validated_type(uuidutils.is_uuid_like),
}


class APIValidator(jsonschema.Draft3Validator):
    # NOTE(oomichi): Use Draft3Validator here, because "required" of
    #                Draft4Validator does not work.
    def __init__(self, schema):
        super(APIValidator, self).__init__(schema, types=types)

    def validate_minimum(self, minimum, instance, schema):
        try:
            # NOTE(oomichi): Orignal validate_minimum() doesn't allow a string
            #                number such as "10", so we need here to support a
            #                string number.
            value = float(instance)
        except ValueError:
            return
        return super(APIValidator, self).validate_minimum(minimum,
                                                          value, schema)

    def validate_maximum(self, maximum, instance, schema):
        try:
            value = float(instance)
        except ValueError:
            return
        return super(APIValidator, self).validate_maximum(maximum,
                                                          value, schema)
