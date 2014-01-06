# Copyright (c) 2013 VMware, Inc.
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
Classes for making VMware VI SOAP calls.
"""

import httplib
import suds

from openstack.common.gettextutils import _  # noqa
from openstack.common.vmware import exceptions
from openstack.common.vmware import vim_util


RESP_NOT_XML_ERROR = "Response is 'text/html', not 'text/xml'"
CONN_ABORT_ERROR = 'Software caused connection abort'
ADDRESS_IN_USE_ERROR = 'Address already in use'


class VimMessagePlugin(suds.plugin.MessagePlugin):
    """Suds plug-in handling some special cases while calling VI SDK."""

    def add_attribute_for_value(self, node):
        """Helper to handle AnyType.

        Suds does not handle AnyType properly. But VI SDK requires type
        attribute to be set when AnyType is used.

        :param node: XML value node
        """
        if node.name == 'value':
            node.set('xsi:type', 'xsd:string')

    def marshalled(self, context):
        """Modifies the envelope document before it is sent.

        Provides the plug-in with the opportunity to prune empty nodes and fix
        nodes before sending it to the server.

        :param context: send context
        """
        # Suds builds the entire request object based on the wsdl schema.
        # VI SDK throws server errors if optional SOAP nodes are sent
        # without values; e.g., <test/> as opposed to <test>test</test>.
        context.envelope.prune()
        context.envelope.walk(self.add_attribute_for_value)


class Vim(object):
    """VIM API Client."""

    def __init__(self, protocol='https', host='localhost', wsdl_loc=None):
        """Create communication interfaces for initiating SOAP transactions.

        :param protocol: http or https
        :param host: Server IP address[:port] or host name[:port]
        """
        if not wsdl_loc:
            wsdl_loc = Vim._get_wsdl_loc(protocol, host)
        soap_url = Vim._get_soap_url(protocol, host)
        self._client = suds.client.Client(wsdl_loc, location=soap_url,
                                          plugins=[VimMessagePlugin()])
        self._service_content = self.RetrieveServiceContent('ServiceInstance')

    @staticmethod
    def _get_wsdl_loc(protocol, host):
        """Return the default WSDL file loclation hosted at the server.

        :param protocol: http or https
        :param host: Server IP address[:port] or host name[:port]
        :return: Default WSDL file location hosted at the server
        """
        return '%s://%s/sdk/vimService.wsdl' % (protocol, host)

    @staticmethod
    def _get_soap_url(protocol, host):
        """Return URL of ESX/VC server's SOAP service.

        :param protocol: https or http
        :param host: Server IP address[:port] or host name[:port]
        :return: URL of ESX/VC server's SOAP service
        """
        return '%s://%s/sdk' % (protocol, host)

    @property
    def service_content(self):
        return self._service_content

    @property
    def client(self):
        return self._client

    @staticmethod
    def _retrieve_properties_ex_fault_checker(response):
        """Checks the RetrievePropertiesEx response for errors.

        Certain faults are sent in the SOAP body as a property of
        missingSet; for example, NotAuthenticated fault. This method
        raises VimFaultException when an error is found.

        :param response: Response from RetrievePropertiesEx API call
        """

        fault_list = []
        if not response:
            # This is the case when the session has timed out. ESX SOAP
            # server sends an empty response. Normally missingSet property
            # has the specifics about the error, but that's not the case
            # with a timed out idle session. It is as bad as a terminated
            # session for we cannot use the session. So setting fault to
            # NotAuthenticated fault.
            fault_list = [exceptions.VimFaultException.NOT_AUTHENTICATED]
        else:
            for obj_cont in response.objects:
                if hasattr(obj_cont, 'missingSet'):
                    for missing_elem in obj_cont.missingSet:
                        fault_type = missing_elem.fault.fault.__class__
                        fault_list.append(fault_type.__name__)
        if fault_list:
            exc_msg_list = ', '.join(fault_list)
            raise exceptions.VimFaultException(fault_list,
                                               _("Error(s): %s occurred "
                                                 "while calling "
                                                 "RetrievePropertiesEx.") %
                                               exc_msg_list)

    def __getattr__(self, attr_name):
        """Makes the API call and gets the result."""

        def vim_request_handler(managed_object, **kwargs):
            """Handler for VIM API calls.

            Builds the SOAP message and parses the response for fault
            checking and other errors.

            :param managed_object:Managed object reference
            :param kwargs: Keyword arguments of the call
            :return: Response of the API call
            """

            try:
                if isinstance(managed_object, str):
                    # For strings use string value for value and type
                    # of the managed object.
                    managed_object = vim_util.get_moref(managed_object,
                                                        managed_object)
                request = getattr(self.client.service, attr_name)
                response = request(managed_object, **kwargs)
                if (attr_name.lower() == 'retrievepropertiesex'):
                    Vim._retrieve_properties_ex_fault_checker(response)
                return response

            except exceptions.VimFaultException as excep:
                raise

            except suds.WebFault as excep:
                doc = excep.document
                detail = doc.childAtPath('/Envelope/Body/Fault/detail')
                fault_list = []
                for child in detail.getChildren():
                    fault_list.append(child.get('type'))
                raise exceptions.VimFaultException(fault_list, str(excep))

            except AttributeError as excep:
                raise exceptions.VimAttributeException(_("No such SOAP method "
                                                         "%(attr)s. Detailed "
                                                         "error: %(excep)s.") %
                                                       {'attr': attr_name,
                                                        'excep': excep})

            except (httplib.CannotSendRequest,
                    httplib.ResponseNotReady,
                    httplib.CannotSendHeader) as excep:
                raise exceptions.SessionOverLoadException(_("httplib error in "
                                                            "%(attr)s: "
                                                            "%(excep)s.") %
                                                          {'attr': attr_name,
                                                           'excep': excep})

            except Exception as excep:
                # Socket errors which need special handling for they
                # might be caused by server API call overload
                if (str(excep).find(ADDRESS_IN_USE_ERROR) != -1 or
                        str(excep).find(CONN_ABORT_ERROR)) != -1:
                    raise exceptions.SessionOverLoadException(_("Socket error "
                                                                "in %(attr)s: "
                                                                "%(excep)s.") %
                                                              {'attr':
                                                               attr_name,
                                                               'excep': excep})
                # Type error that needs special handling for it might be
                # caused by server API call overload
                elif str(excep).find(RESP_NOT_XML_ERROR) != -1:
                    raise exceptions.SessionOverLoadException(_("Type error "
                                                                "in %(attr)s: "
                                                                "%(excep)s.") %
                                                              {'attr':
                                                               attr_name,
                                                               'excep': excep})
                else:
                    raise exceptions.VimException(_("Error in %(attr)s. "
                                                    "Detailed error: "
                                                    "%(excep)s.") %
                                                  {'attr': attr_name,
                                                   'excep': excep})
        return vim_request_handler

    def __repr__(self):
        return "VIM Object."

    def __str__(self):
        return "VIM Object."
