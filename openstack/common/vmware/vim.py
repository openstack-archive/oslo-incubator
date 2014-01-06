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
import urllib2

import suds


from openstack.common.gettextutils import _
from openstack.common import log as logging
from openstack.common.vmware import exceptions
from openstack.common.vmware import vim_util


ADDRESS_IN_USE_ERROR = 'Address already in use'
CONN_ABORT_ERROR = 'Software caused connection abort'
RESP_NOT_XML_ERROR = "Response is 'text/html', not 'text/xml'"

LOG = logging.getLogger(__name__)


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

        This method provides the plug-in with the opportunity to prune empty
        nodes and fix nodes before sending it to the server.

        :param context: send context
        """
        # Suds builds the entire request object based on the WSDL schema.
        # VI SDK throws server errors if optional SOAP nodes are sent
        # without values; e.g., <test/> as opposed to <test>test</test>.
        context.envelope.prune()
        context.envelope.walk(self.add_attribute_for_value)


class Vim(object):
    """VIM API Client."""

    def __init__(self, protocol='https', host='localhost', wsdl_loc=None):
        """Create communication interfaces for initiating SOAP transactions.

        :param protocol: http or https
        :param host: server IP address[:port] or host name[:port]
        :param wsdl_loc: WSDL file location
        :raises: VimException, VimFaultException, VimAttributeException,
                 VimSessionOverLoadException, VimConnectionException
        """
        if not wsdl_loc:
            wsdl_loc = Vim._get_wsdl_loc(protocol, host)
        soap_url = Vim._get_soap_url(protocol, host)
        self._client = suds.client.Client(wsdl_loc,
                                          location=soap_url,
                                          plugins=[VimMessagePlugin()])
        self._service_content = self.RetrieveServiceContent('ServiceInstance')

    @staticmethod
    def _get_wsdl_loc(protocol, host):
        """Get the default WSDL file location hosted at the server.

        :param protocol: http or https
        :param host: server IP address[:port] or host name[:port]
        :returns: default WSDL file location hosted at the server
        """
        return '%s://%s/sdk/vimService.wsdl' % (protocol, host)

    @staticmethod
    def _get_soap_url(protocol, host):
        """Get ESX/VC server's SOAP service URL.

        :param protocol: http or https
        :param host: server IP address[:port] or host name[:port]
        :returns: URL of ESX/VC server's SOAP service
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
        """Checks the RetrievePropertiesEx API response for errors.

        Certain faults are sent in the SOAP body as a property of missingSet.
        This method raises VimFaultException when a fault is found in the
        response.

        :param response: response from RetrievePropertiesEx API call
        :raises: VimFaultException
        """
        LOG.debug(_("Checking RetrievePropertiesEx API response for faults."))
        fault_list = []
        if not response:
            # This is the case when the session has timed out. ESX SOAP
            # server sends an empty RetrievePropertiesExResponse. Normally
            # missingSet in the response objects has the specifics about
            # the error, but that's not the case with a timed out idle
            # session. It is as bad as a terminated session for we cannot
            # use the session. Therefore setting fault to NotAuthenticated
            # fault.
            LOG.debug(_("RetrievePropertiesEx API response is empty; setting "
                        "fault to %s."),
                      exceptions.NOT_AUTHENTICATED_FAULT)
            fault_list = [exceptions.NOT_AUTHENTICATED_FAULT]
        else:
            for obj_cont in response.objects:
                if hasattr(obj_cont, 'missingSet'):
                    for missing_elem in obj_cont.missingSet:
                        fault_type = missing_elem.fault.fault.__class__
                        fault_list.append(fault_type.__name__)
        if fault_list:
            LOG.error(_("Faults %s found in RetrievePropertiesEx API "
                        "response."),
                      fault_list)
            raise exceptions.VimFaultException(fault_list,
                                               _("Error occurred while calling"
                                                 " RetrievePropertiesEx."))
        LOG.debug(_("No faults found in RetrievePropertiesEx API response."))

    def __getattr__(self, attr_name):
        """Returns the method to invoke API identified by param attr_name."""

        def vim_request_handler(managed_object, **kwargs):
            """Handler for VIM API calls.

            Invokes the API and parses the response for fault checking and
            other errors.

            :param managed_object: managed object reference argument of the
                                   API call
            :param kwargs: keyword arguments of the API call
            :returns: response of the API call
            :raises: VimException, VimFaultException, VimAttributeException,
                     VimSessionOverLoadException, VimConnectionException
            """
            try:
                if isinstance(managed_object, str):
                    # For strings, use string value for value and type
                    # of the managed object.
                    managed_object = vim_util.get_moref(managed_object,
                                                        managed_object)
                request = getattr(self.client.service, attr_name)
                LOG.debug(_("Invoking %(attr_name)s on %(moref)s."),
                          {'attr_name': attr_name,
                           'moref': managed_object})
                response = request(managed_object, **kwargs)
                if (attr_name.lower() == 'retrievepropertiesex'):
                    Vim._retrieve_properties_ex_fault_checker(response)
                LOG.debug(_("Invocation of %(attr_name)s on %(moref)s "
                            "completed successfully."),
                          {'attr_name': attr_name,
                           'moref': managed_object})
                return response
            except exceptions.VimFaultException:
                # Catch the VimFaultException that is raised by the fault
                # check of the SOAP response.
                raise

            except suds.WebFault as excep:
                doc = excep.document
                detail = doc.childAtPath('/Envelope/Body/Fault/detail')
                fault_list = []
                for child in detail.getChildren():
                    fault_list.append(child.get('type'))
                raise exceptions.VimFaultException(
                    fault_list, _("Web fault in %s.") % attr_name, excep)

            except AttributeError as excep:
                raise exceptions.VimAttributeException(
                    _("No such SOAP method %s.") % attr_name, excep)

            except (httplib.CannotSendRequest,
                    httplib.ResponseNotReady,
                    httplib.CannotSendHeader) as excep:
                raise exceptions.VimSessionOverLoadException(
                    _("httplib error in %s.") % attr_name, excep)

            except (urllib2.URLError, urllib2.HTTPError) as excep:
                raise exceptions.VimConnectionException(
                    _("urllib2 error in %s.") % attr_name, excep)

            except Exception as excep:
                # TODO(vbala) should catch specific exceptions and raise
                # appropriate VimExceptions.

                # Socket errors which need special handling; some of these
                # might be caused by server API call overload.
                if (str(excep).find(ADDRESS_IN_USE_ERROR) != -1 or
                        str(excep).find(CONN_ABORT_ERROR)) != -1:
                    raise exceptions.VimSessionOverLoadException(
                        _("Socket error in %s.") % attr_name, excep)
                # Type error which needs special handling; it might be caused
                # by server API call overload.
                elif str(excep).find(RESP_NOT_XML_ERROR) != -1:
                    raise exceptions.VimSessionOverLoadException(
                        _("Type error in %s.") % attr_name, excep)
                else:
                    raise exceptions.VimException(
                        _("Exception in %s.") % attr_name, excep)
        return vim_request_handler

    def __repr__(self):
        return "VIM Object."

    def __str__(self):
        return "VIM Object."
