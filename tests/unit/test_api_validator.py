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

from openstack.common import api_validator
from openstack.common import exception
from tests import utils


class APIValidatorTestCase(utils.BaseTestCase):

    def test_validate_required(self):
        schema = {
            'type': 'object',
            'properties': {
                'foo': {
                    'type': 'integer',
                },
            },
            'required': ['foo']
        }
        validator = api_validator.APIValidator(schema)
        validator.validate({'foo': 1})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'abc': 1})

    def test_validate_string(self):
        schema = {
            'type': 'object',
            'properties': {
                'foo': {
                    'type': 'string',
                },
            },
        }
        validator = api_validator.APIValidator(schema)
        validator.validate({'foo': 'abc'})
        validator.validate({'foo': '0'})
        validator.validate({'foo': ''})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': 1})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': 1.5})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': True})

    def test_validate_string_with_length(self):
        schema = {
            'type': 'object',
            'properties': {
                'foo': {
                    'type': 'string', 'minLength': 1, 'maxLength': 10,
                },
            },
        }
        validator = api_validator.APIValidator(schema)
        validator.validate({'foo': '0'})
        validator.validate({'foo': '0123456789'})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': ''})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': '0123456789a'})

    def test_validate_integer(self):
        schema = {
            'type': 'object',
            'properties': {
                'foo': {
                    'type': ['integer', 'string'],
                    'format': 'integer',
                },
            },
        }
        validator = api_validator.APIValidator(schema)

        validator.validate({'foo': 1})
        validator.validate({'foo': '1'})
        validator.validate({'foo': '0123456789'})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': 'abc'})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': True})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': '0xffff'})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': 1.0})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': '1.0'})

    def test_validate_integer_with_range(self):
        schema = {
            'type': 'object',
            'properties': {
                'foo': {
                    'type': ['integer', 'string'],
                    'format': 'integer',
                    'minimum': 1,
                    'maximum': 10,
                },
            },
        }
        validator = api_validator.APIValidator(schema)

        validator.validate({'foo': 1})
        validator.validate({'foo': 10})
        validator.validate({'foo': '1'})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': 0})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': 11})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': '0'})

    def test_validate_uuid(self):
        schema = {
            'type': 'object',
            'properties': {
                'foo': {
                    'type': 'uuid',
                },
            },
        }
        validator = api_validator.APIValidator(schema)
        validator.validate({'foo': '70a599e0-31e7-49b7-b260-868f441e862b'})
        self.assertRaises(exception.ValidationError,
                          validator.validate,
                          {'foo': '70a599e031e749b7b260868f441e862b'})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': 1})
        self.assertRaises(exception.ValidationError,
                          validator.validate, {'foo': 'abc'})
