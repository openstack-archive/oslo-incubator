# Copyright (c) 2014 VMware, Inc.
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
Unit tests for classes to invoke VMware VI SOAP calls.
"""

import httplib
import urllib2

import mock
import suds

from openstack.common import test
from openstack.common.vmware import exceptions
from openstack.common.vmware import vim


class VimMessagePluginTest(test.BaseTestCase):
    """Test class for VimMessagePlugin."""

    def test_add_attribute_for_value(self):
        node = mock.Mock()
        node.name = 'value'
        plugin = vim.VimMessagePlugin()
        plugin.add_attribute_for_value(node)
        node.set.assert_called_once_with('xsi:type', 'xsd:string')

    def test_marshalled(self):
        plugin = vim.VimMessagePlugin()
        context = mock.Mock()
        plugin.marshalled(context)
        context.envelope.prune.assert_called_once_with()
        context.envelope.walk.assert_called_once_with(
            plugin.add_attribute_for_value)


class VimTest(test.BaseTestCase):
    """Test class for Vim."""

    def setUp(self):
        super(VimTest, self).setUp()
        patcher = mock.patch('suds.client.Client')
        self.addCleanup(patcher.stop)
        self.SudsClientMock = patcher.start()

    @mock.patch.object(vim.Vim, '__getattr__', autospec=True)
    def test_init(self, getattr_mock):
        getattr_ret = mock.Mock()
        getattr_mock.side_effect = lambda *args: getattr_ret
        vim_obj = vim.Vim()
        getattr_mock.assert_called_once_with(vim_obj, 'RetrieveServiceContent')
        getattr_ret.assert_called_once_with('ServiceInstance')
        self.assertEqual(self.SudsClientMock.return_value, vim_obj.client)
        self.assertEqual(getattr_ret.return_value, vim_obj.service_content)

    def test_retrieve_properties_ex_fault_checker_with_empty_response(self):
        try:
            vim.Vim._retrieve_properties_ex_fault_checker(None)
            assert False
        except exceptions.VimFaultException as ex:
            self.assertEqual([exceptions.NOT_AUTHENTICATED_FAULT],
                             ex.fault_list)

    def test_retrieve_properties_ex_fault_checker(self):
        fault_list = ['FileFault', 'VimFault']
        missing_set = []
        for fault in fault_list:
            missing_elem = mock.Mock()
            missing_elem.fault.fault.__class__.__name__ = fault
            missing_set.append(missing_elem)
        obj_cont = mock.Mock()
        obj_cont.missingSet = missing_set
        response = mock.Mock()
        response.objects = [obj_cont]

        try:
            vim.Vim._retrieve_properties_ex_fault_checker(response)
            assert False
        except exceptions.VimFaultException as ex:
            self.assertEqual(fault_list, ex.fault_list)

    def test_vim_request_handler(self):
        managed_object = 'VirtualMachine'
        resp = mock.Mock()

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo.type)
            self.assertEqual(managed_object, mo.value)
            return resp

        vim_obj = vim.Vim()
        attr_name = 'powerOn'
        service_mock = vim_obj._client.service
        setattr(service_mock, attr_name, side_effect)
        ret = vim_obj.powerOn(managed_object)
        self.assertEqual(resp, ret)

    def test_vim_request_handler_with_retrieve_properties_ex_fault(self):
        managed_object = 'Datacenter'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo.type)
            self.assertEqual(managed_object, mo.value)
            return None

        vim_obj = vim.Vim()
        attr_name = 'retrievePropertiesEx'
        service_mock = vim_obj._client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exceptions.VimFaultException,
                          lambda: vim_obj.retrievePropertiesEx(managed_object))

    def test_vim_request_handler_with_web_fault(self):
        managed_object = 'VirtualMachine'
        fault_list = ['Fault']

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo.type)
            self.assertEqual(managed_object, mo.value)
            doc = mock.Mock()
            detail = doc.childAtPath.return_value
            child = mock.Mock()
            child.get.return_value = fault_list[0]
            detail.getChildren.return_value = [child]
            raise suds.WebFault(None, doc)

        vim_obj = vim.Vim()
        attr_name = 'powerOn'
        service_mock = vim_obj._client.service
        setattr(service_mock, attr_name, side_effect)

        try:
            vim_obj.powerOn(managed_object)
        except exceptions.VimFaultException as ex:
            self.assertEqual(fault_list, ex.fault_list)

    def test_vim_request_handler_with_attribute_error(self):
        managed_object = 'VirtualMachine'
        vim_obj = vim.Vim()
        # no powerOn method in Vim
        service_mock = mock.Mock(spec=vim.Vim)
        vim_obj._client.service = service_mock
        self.assertRaises(exceptions.VimAttributeException,
                          lambda: vim_obj.powerOn(managed_object))

    def test_vim_request_handler_with_http_cannot_send_error(self):
        managed_object = 'VirtualMachine'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo.type)
            self.assertEqual(managed_object, mo.value)
            raise httplib.CannotSendRequest()

        vim_obj = vim.Vim()
        attr_name = 'powerOn'
        service_mock = vim_obj._client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exceptions.VimSessionOverLoadException,
                          lambda: vim_obj.powerOn(managed_object))

    def test_vim_request_handler_with_http_response_not_ready_error(self):
        managed_object = 'VirtualMachine'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo.type)
            self.assertEqual(managed_object, mo.value)
            raise httplib.ResponseNotReady()

        vim_obj = vim.Vim()
        attr_name = 'powerOn'
        service_mock = vim_obj._client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exceptions.VimSessionOverLoadException,
                          lambda: vim_obj.powerOn(managed_object))

    def test_vim_request_handler_with_http_cannot_send_header_error(self):
        managed_object = 'VirtualMachine'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo.type)
            self.assertEqual(managed_object, mo.value)
            raise httplib.CannotSendHeader()

        vim_obj = vim.Vim()
        attr_name = 'powerOn'
        service_mock = vim_obj._client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exceptions.VimSessionOverLoadException,
                          lambda: vim_obj.powerOn(managed_object))

    def test_vim_request_handler_with_url_error(self):
        managed_object = 'VirtualMachine'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo.type)
            self.assertEqual(managed_object, mo.value)
            raise urllib2.URLError(None)

        vim_obj = vim.Vim()
        attr_name = 'powerOn'
        service_mock = vim_obj._client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exceptions.VimConnectionException,
                          lambda: vim_obj.powerOn(managed_object))

    def test_vim_request_handler_with_http_error(self):
        managed_object = 'VirtualMachine'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo.type)
            self.assertEqual(managed_object, mo.value)
            raise urllib2.HTTPError(None, None, None, None, None)

        vim_obj = vim.Vim()
        attr_name = 'powerOn'
        service_mock = vim_obj._client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exceptions.VimConnectionException,
                          lambda: vim_obj.powerOn(managed_object))

    def _test_vim_request_handler_with_exception(self, message, exception):
        managed_object = 'VirtualMachine'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo.type)
            self.assertEqual(managed_object, mo.value)
            raise Exception(message)

        vim_obj = vim.Vim()
        attr_name = 'powerOn'
        service_mock = vim_obj._client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exception, lambda: vim_obj.powerOn(managed_object))

    def test_vim_request_handler_with_address_in_use_error(self):
        self._test_vim_request_handler_with_exception(
            vim.ADDRESS_IN_USE_ERROR, exceptions.VimSessionOverLoadException)

    def test_vim_request_handler_with_conn_abort_error(self):
        self._test_vim_request_handler_with_exception(
            vim.CONN_ABORT_ERROR, exceptions.VimSessionOverLoadException)

    def test_vim_request_handler_with_resp_not_xml_error(self):
        self._test_vim_request_handler_with_exception(
            vim.RESP_NOT_XML_ERROR, exceptions.VimSessionOverLoadException)

    def test_vim_request_handler_with_generic_error(self):
        self._test_vim_request_handler_with_exception(
            'GENERIC_ERROR', exceptions.VimException)
