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
Utility functions for image transfer.
"""

from eventlet import timeout

from openstack.common.gettextutils import _  # noqa
from openstack.common import log as logging
from openstack.common.vmware import exceptions
from openstack.common.vmware import io_util
from openstack.common.vmware import read_write_util as rw_util

LOG = logging.getLogger(__name__)

QUEUE_BUFFER_SIZE = 10


def start_transfer(context, timeout_secs, read_file_handle, max_data_size,
                   write_file_handle=None, image_service=None, image_id=None,
                   image_meta=None):
    """Start the data transfer from the reader to the writer.

    Reader writes to the pipe and the writer reads from the pipe. This means
    that the total transfer time boils down to the slower of the read/write
    and not the addition of the two times.
    """

    if not image_meta:
        image_meta = {}

    # The pipe that acts as an intermediate store of data for reader to write
    # to and writer to grab from.
    thread_safe_pipe = io_util.ThreadSafePipe(QUEUE_BUFFER_SIZE, max_data_size)
    # The read thread. In case of glance, the read_file_handle is an instance
    # of the GlanceFileRead class. The glance client read returns an iterator
    # and the IOThread class wraps that iterator to provide datachunks in calls
    # to read.
    read_thread = io_util.IOThread(read_file_handle, thread_safe_pipe)

    # In case of Glance - VMware transfer, we just need a handle to the
    # HTTP Connection to transfer data to the VMware datastore.
    if write_file_handle:
        write_thread = io_util.IOThread(thread_safe_pipe, write_file_handle)
    # In case of VMware - Glance transfer, we should ensure that the glance
    # image status to be active. This is handled by GlanceWriteThread.
    elif image_service and image_id:
        write_thread = io_util.GlanceWriteThread(context, thread_safe_pipe,
                                                 image_service, image_id,
                                                 image_meta)
    # Start the read and write threads.
    read_event = read_thread.start()
    write_event = write_thread.start()
    timer = timeout.Timeout(timeout_secs)
    try:
        # Wait on the read and write events to signal the completion
        read_event.wait()
        write_event.wait()
    except (timeout.Timeout, Exception) as exc:
        read_thread.stop()
        write_thread.stop()

        LOG.exception(exc)
        raise exceptions.ImageTransferException(exc)
    finally:
        timer.cancel()
        read_file_handle.close()
        if write_file_handle:
            write_file_handle.close()


def fetch_flat_image(context, timeout_secs, image_service, image_id, **kwargs):
    """Download flat image from the glance image server."""

    LOG.debug(_("Downloading image: %s from glance image server as a flat vmdk"
                " file.") % image_id)
    file_size = int(kwargs.get('image_size'))
    read_iter = image_service.download(context, image_id)
    read_handle = rw_util.GlanceFileRead(read_iter)
    write_handle = rw_util.VMwareHTTPWriteFile(kwargs.get('host'),
                                               kwargs.get('data_center_name'),
                                               kwargs.get('datastore_name'),
                                               kwargs.get('cookies'),
                                               kwargs.get('file_path'),
                                               file_size)
    start_transfer(context, timeout_secs, read_handle, file_size,
                   write_file_handle=write_handle)
    LOG.info(_("Downloaded image: %s from glance image server.") % image_id)


def fetch_stream_optimized_image(context, timeout_secs, image_service,
                                 image_id, **kwargs):
    """Download stream optimized image from glance image server."""

    LOG.debug(_("Downloading image: %s from glance image server using HttpNfc"
                " import.") % image_id)
    file_size = int(kwargs.get('image_size'))
    read_iter = image_service.download(context, image_id)
    read_handle = rw_util.GlanceFileRead(read_iter)
    write_handle = rw_util.VMwareHTTPWriteVmdk(kwargs.get('session'),
                                               kwargs.get('host'),
                                               kwargs.get('resource_pool'),
                                               kwargs.get('vm_folder'),
                                               kwargs.get('vm_create_spec'),
                                               file_size)
    start_transfer(context, timeout_secs, read_handle, file_size,
                   write_file_handle=write_handle)
    LOG.info(_("Downloaded image: %s from glance image server.") % image_id)


def upload_image(context, timeout_secs, image_service, image_id, owner_id,
                 **kwargs):
    """Upload the VM's disk file to glance image server."""

    LOG.debug(_("Uploading image: %s to the glance image server using HttpNfc"
                " export.") % image_id)
    file_size = kwargs.get('vmdk_size')
    read_handle = rw_util.VMwareHTTPReadVmdk(kwargs.get('session'),
                                             kwargs.get('host'),
                                             kwargs.get('vm'),
                                             kwargs.get('vmdk_file_path'),
                                             file_size)

    # Set the image properties.
    # It is important to set the 'size' to 0. Otherwise, the glance client
    # uses the volume size which may not be the image size after upload since
    # it is converted to a stream-optimized sparse disk.
    image_metadata = {'disk_format': 'vmdk',
                      'is_public': 'false',
                      'name': kwargs.get('image_name'),
                      'status': 'active',
                      'container_format': 'bare',
                      'size': 0,
                      'properties': {'vmware_image_version':
                                     kwargs.get('image_version'),
                                     'vmware_disktype': 'streamOptimized',
                                     'owner_id': owner_id}}
    start_transfer(context, timeout_secs, read_handle, file_size,
                   image_service=image_service, image_id=image_id,
                   image_meta=image_metadata)
    LOG.info(_("Uploaded image: %s to the glance image server.") % image_id)
