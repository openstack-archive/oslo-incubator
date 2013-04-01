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


@jsonschema.FormatChecker.cls_checks('integer')
def validate_integer_format(instance):
    try:
        int(instance)
    except ValueError:
        return False
    else:
        return True


@jsonschema.FormatChecker.cls_checks('uuid')
def validate_uuid_format(instance):
    return uuidutils.is_uuid_like(instance)


class APIValidator(jsonschema.Draft4Validator):
    def __init__(self, schema):
        format_checker = jsonschema.FormatChecker()
        super(APIValidator, self).__init__(schema,
                                           format_checker=format_checker)

    def _number_from_str(self, instance):
        # NOTE(oomichi): Orignal validate_minimum() doesn't allow a string
        #                number such as "10", so we need here to support a
        #                string number.
        try:
            value = int(instance)
        except (ValueError, TypeError):
            try:
                value = float(instance)
            except (ValueError, TypeError):
                return None
        return value

    def validate_minimum(self, minimum, instance, schema):
        value = self._number_from_str(instance)
        if value is None:
            return
        return super(APIValidator, self).validate_minimum(minimum,
                                                          value, schema)

    def validate_maximum(self, maximum, instance, schema):
        value = self._number_from_str(instance)
        if value is None:
            return
        return super(APIValidator, self).validate_maximum(maximum,
                                                          value, schema)
