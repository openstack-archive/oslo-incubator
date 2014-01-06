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
Classes to handle image files.

Collection of classes to handle image upload/download to/from image service
(like Glance image storage and retrieval service) from/to VMware server.
"""

import httplib
import netaddr
import urllib
import urllib2
import urlparse

from openstack.common.gettextutils import _  # noqa
from openstack.common import log as logging
from openstack.common.vmware import exceptions
from openstack.common.vmware import vim_util

LOG = logging.getLogger(__name__)
USER_AGENT = 'OpenStack-ESX-Adapter'
READ_CHUNKSIZE = 65536


class GlanceFileRead(object):
    """Glance file read handler class."""

    def __init__(self, glance_read_iter):
        self.glance_read_iter = glance_read_iter
        self.iter = self.get_next()

    def read(self, chunk_size):
        """Read an item from the queue.

        The input chunk size is ignored since the client ImageBodyIterator
        uses its own CHUNKSIZE.
        """
        try:
            return self.iter.next()
        except StopIteration:
            return ""

    def get_next(self):
        """Get the next item from the image iterator."""
        for data in self.glance_read_iter:
            yield data

    def close(self):
        """A dummy close just to maintain consistency."""
        pass


class VMwareHTTPFile(object):
    """Base class for VMDK file access over HTTP."""

    def __init__(self, file_handle):
        self.eof = False
        self.file_handle = file_handle

    def close(self):
        """Close the file handle."""
        try:
            self.file_handle.close()
        except Exception as exc:
            LOG.exception(exc)

    def __del__(self):
        """Close the file handle on garbage collection."""
        self.close()

    def _build_vim_cookie_headers(self, vim_cookies):
        """Build ESX host session cookie headers."""
        cookie_header = ""
        for vim_cookie in vim_cookies:
            cookie_header = vim_cookie.name + '=' + vim_cookie.value
            break
        return cookie_header

    def write(self, data):
        """Write data to the file."""
        raise NotImplementedError()

    def read(self, chunk_size):
        """Read a chunk of data."""
        raise NotImplementedError()

    def get_size(self):
        """Get size of the file to be read."""
        raise NotImplementedError()

    def _is_valid_ipv6(self, address):
        """Whether given host address is a valid IPv6 address."""
        try:
            return netaddr.valid_ipv6(address)
        except Exception:
            return False

    def get_soap_url(self, scheme, host):
        """return IPv4/v6 compatible url constructed for host."""
        if self._is_valid_ipv6(host):
            return '%s://[%s]' % (scheme, host)
        return '%s://%s' % (scheme, host)

    def _fix_esx_url(self, url, host):
        """Fix netloc in the case of an ESX host.

        In the case of an ESX host, the netloc is set to '*' in the url
        returned in HttpNfcLeaseInfo. It should be replaced with host name
        or IP address.
        """
        urlp = urlparse.urlparse(url)
        if urlp.netloc == '*':
            scheme, netloc, path, params, query, fragment = urlp
            url = urlparse.urlunparse((scheme, host, path, params,
                                       query, fragment))
        return url

    def find_vmdk_url(self, lease_info, host):
        """Find the URL corresponding to a vmdk disk in lease info."""
        url = None
        for deviceUrl in lease_info.deviceUrl:
            if deviceUrl.disk:
                url = self._fix_esx_url(deviceUrl.url, host)
                break
        return url


class VMwareHTTPWriteFile(VMwareHTTPFile):
    """VMware file write handler class."""

    def __init__(self, host, data_center_name, datastore_name, cookies,
                 file_path, file_size, scheme='https'):
        soap_url = self.get_soap_url(scheme, host)
        base_url = '%s/folder/%s' % (soap_url, file_path)
        param_list = {'dcPath': data_center_name, 'dsName': datastore_name}
        base_url = base_url + '?' + urllib.urlencode(param_list)
        _urlparse = urlparse.urlparse(base_url)
        scheme, netloc, path, params, query, fragment = _urlparse

        if scheme == 'http':
            conn = httplib.HTTPConnection(netloc)
        elif scheme == 'https':
            conn = httplib.HTTPSConnection(netloc)
        conn.putrequest('PUT', path + '?' + query)
        conn.putheader('User-Agent', USER_AGENT)
        conn.putheader('Content-Length', file_size)
        conn.putheader('Cookie', self._build_vim_cookie_headers(cookies))
        conn.endheaders()
        self.conn = conn
        VMwareHTTPFile.__init__(self, conn)

    def write(self, data):
        """Write to the file."""
        self.file_handle.send(data)

    def close(self):
        """Get the response and close the connection."""
        try:
            self.conn.getresponse()
        except Exception as excep:
            LOG.debug(_("Exception during HTTP connection close in "
                        "VMwareHTTPWriteFile. Exception is %s.") % excep)
        super(VMwareHTTPWriteFile, self).close()


class VMwareHTTPWriteVmdk(VMwareHTTPFile):
    """Class to write VMDK over HTTP using VMware HttpNfcLease."""

    def __init__(self, session, host, rp_ref, vm_folder_ref, vm_create_spec,
                 vmdk_size):
        """Initialize a writer for vmdk file.

        :param session: Valid api session to ESX/VC server
        :param host: ESX or VC host IP
        :param rp_ref: Resource pool into which backing VM is imported
        :param vm_folder_ref: VM folder in ESX/VC inventory to use as parent
                              of backing VM
        :param vm_create_spec: Create spec of backing VM
        :param vmdk_size: Size of the backing VM's vmdk file
        """
        self._session = session
        self._vmdk_size = vmdk_size
        self._progress = 0
        lease = session.invoke_api(session.vim, 'ImportVApp', rp_ref,
                                   spec=vm_create_spec, folder=vm_folder_ref)
        session.wait_for_lease_ready(lease)
        self._lease = lease
        lease_info = session.invoke_api(vim_util, 'get_object_property',
                                        session.vim, lease, 'info')
        # Find the url of vmdk device
        url = self.find_vmdk_url(lease_info, host)
        if not url:
            msg = _("Could not retrieve URL from lease.")
            LOG.exception(msg)
            raise exceptions.VimException(msg)
        LOG.info(_("Opening vmdk url: %s for write.") % url)

        # Prepare the http connection to the vmdk url
        cookies = session.vim.client.options.transport.cookiejar
        _urlparse = urlparse.urlparse(url)
        scheme, netloc, path, params, query, fragment = _urlparse

        if scheme == 'http':
            conn = httplib.HTTPConnection(netloc)
        elif scheme == 'https':
            conn = httplib.HTTPSConnection(netloc)
        if query:
            path = path + '?' + query
        conn.putrequest('PUT', path)
        conn.putheader('User-Agent', USER_AGENT)
        conn.putheader('Content-Length', str(vmdk_size))
        conn.putheader('Overwrite', 't')
        conn.putheader('Cookie', self._build_vim_cookie_headers(cookies))
        conn.putheader('Content-Type', 'binary/octet-stream')
        conn.endheaders()
        self.conn = conn
        VMwareHTTPFile.__init__(self, conn)

    def write(self, data):
        """Write to the file."""
        self._progress += len(data)
        LOG.debug(_("Written %s bytes to vmdk.") % self._progress)
        self.file_handle.send(data)

    def update_progress(self):
        """Updates progress to lease.

        This call back to the lease is essential to keep the lease alive
        across long running write operations.
        """
        percent = int(float(self._progress) / self._vmdk_size * 100)
        try:
            LOG.debug(_("Updating progress to %s percent.") % percent)
            self._session.invoke_api(self._session.vim,
                                     'HttpNfcLeaseProgress',
                                     self._lease, percent=percent)
        except exceptions.VimException as ex:
            LOG.exception(ex)
            raise ex

    def close(self):
        """End the lease and close the connection."""
        state = self._session.invoke_api(vim_util, 'get_object_property',
                                         self._session.vim,
                                         self._lease, 'state')
        if state == 'ready':
            self._session.invoke_api(self._session.vim, 'HttpNfcLeaseComplete',
                                     self._lease)
            LOG.debug(_("Lease released."))
        else:
            LOG.debug(_("Lease is already in state: %s.") % state)
        super(VMwareHTTPWriteVmdk, self).close()


class VMwareHTTPReadVmdk(VMwareHTTPFile):
    """Class to read VMDK file over HTTP using VMware HttpNfcLease."""

    def __init__(self, session, host, vm_ref, vmdk_path, vmdk_size):
        """Initialize a reader for vmdk file.

        During an export operation the vmdk disk is converted to a
        stream-optimized sparse disk format. Therefore the size of the VMDK
        after export may be smaller than the current vmdk disk size.

        :param session: Valid api session to ESX/VC server
        :param host: ESX or VC host IP
        :param vm_ref: Backing VM whose vmdk is to be exported
        :param vmdk_path: Datastore relative path to vmdk file to be exported
        :param vmdk_size: Current disk size of vmdk file to be exported
        """
        self._session = session
        self._vmdk_size = vmdk_size
        self._progress = 0
        lease = session.invoke_api(session.vim, 'ExportVm', vm_ref)
        session.wait_for_lease_ready(lease)
        self._lease = lease
        lease_info = session.invoke_api(vim_util, 'get_object_property',
                                        session.vim, lease, 'info')

        # find the disk url corresponding to the given vmdk_path
        url = self.find_vmdk_url(lease_info, host)
        if not url:
            msg = _("Could not retrieve URL from lease.")
            LOG.exception(msg)
            raise exceptions.VimException(msg)
        LOG.info(_("Opening vmdk url: %s for read.") % url)

        cookies = session.vim.client.options.transport.cookiejar
        headers = {'User-Agent': USER_AGENT,
                   'Cookie': self._build_vim_cookie_headers(cookies)}
        request = urllib2.Request(url, None, headers)
        conn = urllib2.urlopen(request)
        VMwareHTTPFile.__init__(self, conn)

    def read(self, chunk_size):
        """Read a chunk from file."""
        self._progress += READ_CHUNKSIZE
        LOG.debug(_("Read %s bytes from vmdk.") % self._progress)
        return self.file_handle.read(READ_CHUNKSIZE)

    def update_progress(self):
        """Updates progress to lease.

        This call back to the lease is essential to keep the lease alive
        across long running read operations.
        """
        percent = int(float(self._progress) / self._vmdk_size * 100)
        try:
            LOG.debug(_("Updating progress to %s percent.") % percent)
            self._session.invoke_api(self._session.vim,
                                     'HttpNfcLeaseProgress',
                                     self._lease, percent=percent)
        except exceptions.VimException as ex:
            LOG.exception(ex)
            raise ex

    def close(self):
        """End the lease and close the connection."""
        state = self._session.invoke_api(vim_util, 'get_object_property',
                                         self._session.vim,
                                         self._lease, 'state')
        if state == 'ready':
            self._session.invoke_api(self._session.vim, 'HttpNfcLeaseComplete',
                                     self._lease)
            LOG.debug(_("Lease released."))
        else:
            LOG.debug(_("Lease is already in state: %s.") % state)
        super(VMwareHTTPReadVmdk, self).close()
