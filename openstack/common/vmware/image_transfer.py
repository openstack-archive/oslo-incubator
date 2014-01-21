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
Functions and classes for image transfer between ESX/VC & image service.
"""

from eventlet import event
from eventlet import greenthread
from eventlet import queue
from eventlet import timeout

from openstack.common.gettextutils import _
from openstack.common import log as logging
from openstack.common.vmware import exceptions
from openstack.common.vmware import rw_handles


LOG = logging.getLogger(__name__)

IMAGE_SERVICE_POLL_INTERVAL = 5
FILE_READ_WRITE_TASK_SLEEP_TIME = 0.01
BLOCKING_QUEUE_SIZE = 10


class BlockingQueue(queue.LightQueue):
    """Producer-Consumer queue to share data between reader/writer threads."""

    def __init__(self, max_size, max_transfer_size):
        """Initializes the queue with the given parameters.

        :param max_size: maximum queue size; if max_size is less than zero or
                         None, the queue size is infinite.
        :param _max_transfer_size: maximum amount of data that can be
                                  _transferred using this queue
        """
        queue.LightQueue.__init__(self, max_size)
        self._max_transfer_size = max_transfer_size
        self._transferred = 0

    def read(self, chunk_size):
        """Read data from the queue.

        This method blocks until data is available. The input chunk size is
        ignored since we have ensured that the data chunks written to the pipe
        by the image reader thread is the same as the chunks asked for by the
        image writer thread.
        """
        if self._transferred < self._max_transfer_size:
            data_item = self.get()
            self._transferred += len(data_item)
            return data_item
        else:
            LOG.debug(_("Completed transfer of size %s."), self._transferred)
            return ""

    def write(self, data):
        """Write data into the queue.

        :param data: data to be written
        """
        LOG.debug(_("Writing %d data items into the queue."), len(data))
        self.put(data)

    # Below NOP methods are provided in order to enable treating the queue
    # as a file handle.
    def seek(self, offset, whence=0):
        pass

    def tell(self):
        """Get size of the file to be read."""
        return self._max_transfer_size

    def close(self):
        pass

    def __str__(self):
        return "blocking queue"


class ImageWriter(object):
    """Class to write the image to the image service from an input file."""

    def __init__(self, context, input_file, image_service, image_id,
                 image_meta=None):
        """Initializes the image writer instance with given parameters.

        :param context: write context needed by the image service
        :param input_file: file to read the image data from
        :param image_service: handle to image service
        :param image_id: ID of the image in the image service
        :param image_meta: image meta-data
        """
        if not image_meta:
            image_meta = {}

        self._context = context
        self._input_file = input_file
        self._image_service = image_service
        self._image_id = image_id
        self._image_meta = image_meta
        self._running = False

    def start(self):
        """Start the image write task.

        :returns: the event indicating the status of the write task
        """
        self._done = event.Event()

        def _inner():
            """Task performing the image write operation.

            This method performs image data transfer through an update call.
            After the update, it waits until the image state becomes
            'active', 'killed' or unknown. If the final state is not 'active'
            an instance of ImageTransferException is thrown.

            :raises: ImageTransferException
            """
            LOG.debug(_("Calling image service update on image: %(image)s "
                        "with meta: %(meta)s"),
                      {'image': self._image_id,
                       'meta': self._image_meta})

            try:
                self._image_service.update(self._context,
                                           self._image_id,
                                           self._image_meta,
                                           data=self._input_file)
                self._running = True
                while self._running:
                    LOG.debug(_("Retrieving status of image: %s."),
                              self._image_id)
                    image_meta = self._image_service.show(self._context,
                                                          self._image_id)
                    image_status = image_meta.get('status')
                    if image_status == 'active':
                        self.stop()
                        LOG.debug(_("Image: %s is now active."),
                                  self._image_id)
                        self._done.send(True)
                    elif image_status == 'killed':
                        self.stop()
                        excep_msg = (_("Image: %s is in killed state.") %
                                     self._image_id)
                        LOG.error(excep_msg)
                        excep = exceptions.ImageTransferException(excep_msg)
                        self._done.send_exception(excep)
                    elif image_status in ['saving', 'queued']:
                        LOG.debug(_("Image: %(image)s is in %(state)s state; "
                                    "sleeping for %(sleep)d seconds."),
                                  {'image': self._image_id,
                                   'state': image_status,
                                   'sleep': IMAGE_SERVICE_POLL_INTERVAL})
                        greenthread.sleep(IMAGE_SERVICE_POLL_INTERVAL)
                    else:
                        self.stop()
                        excep_msg = _("Image: %(image)s is in unknown state: "
                                      "%(state)s.") % {'image': self._image_id,
                                                       'state': image_status}
                        LOG.error(excep_msg)
                        excep = exceptions.ImageTransferException(excep_msg)
                        self._done.send_exception(excep)
            except Exception as excep:
                self.stop()
                excep_msg = (_("Error occurred while writing image: %s") %
                             self._image_id)
                LOG.exception(excep_msg)
                excep = exceptions.ImageTransferException(excep_msg, excep)
                self._done.send_exception(excep)

        LOG.debug(_("Starting image write task for image: %(image)s with"
                    " source: %(source)s."),
                  {'source': self._input_file,
                   'image': self._image_id})
        greenthread.spawn(_inner)
        return self._done

    def stop(self):
        """Stop the image writing task."""
        LOG.debug(_("Stopping the writing task for image: %s."),
                  self._image_id)
        self._running = False

    def wait(self):
        """Wait for the image writer task to complete.

        This method returns True if the writer thread completes successfully.
        In case of error, it raises ImageTransferException.

        :raises ImageTransferException
        """
        return self._done.wait()

    def close(self):
        """This is a NOP."""
        pass

    def __str__(self):
        string = "Image Writer <source = %s, dest = %s>" % (self._input_file,
                                                            self._image_id)
        return string


class FileReadWriteTask(object):
    """Task which reads data from the input file and writes to the output file.

    This class defines the task which copies the given input file to the given
    output file. The copy operation involves reading chunks of data from the
    input file and writing the same to the output file.
    """

    def __init__(self, input_file, output_file):
        """Initializes the read-write task with the given input parameters.

        :param input_file: the input file handle
        :param output_file: the output file handle
        """
        self._input_file = input_file
        self._output_file = output_file
        self._running = False

    def start(self):
        """Start the file read - file write task.

        :returns: the event indicating the status of the read-write task
        """
        self._done = event.Event()

        def _inner():
            """Task performing the file read-write operation."""
            self._running = True
            while self._running:
                try:
                    data = self._input_file.read(None)
                    if not data:
                        LOG.debug(_("File read-write task is done."))
                        self.stop()
                        self._done.send(True)
                    # TODO(vbala) Do we need to write empty data?
                    self._output_file.write(data)

                    # update lease progress if applicable
                    if hasattr(self._input_file, "update_progress"):
                        self._input_file.update_progress()
                    if hasattr(self._output_file, "update_progress"):
                        self._output_file.update_progress()

                    greenthread.sleep(FILE_READ_WRITE_TASK_SLEEP_TIME)
                except Exception as excep:
                    self.stop()
                    excep_msg = _("Error occurred during file read-write "
                                  "task.")
                    LOG.exception(excep_msg)
                    excep = exceptions.ImageTransferException(excep_msg, excep)
                    self._done.send_exception(excep)

        LOG.debug(_("Starting file read-write task with source: %(source)s "
                    "and destination: %(dest)s."),
                  {'source': self._input_file,
                   'dest': self._output_file})
        greenthread.spawn(_inner)
        return self._done

    def stop(self):
        """Stop the read-write task."""
        LOG.debug(_("Stopping the file read-write task."))
        self._running = False

    def wait(self):
        """Wait for the file read-write task to complete.

        This method returns True if the read-write thread completes
        successfully. In case of error, it raises ImageTransferException.

        :raises: ImageTransferException
        """
        return self._done.wait()

    def __str__(self):
        string = ("File Read-Write Task <source = %s, dest = %s>" %
                  (self._input_file, self._output_file))
        return string


# Functions to perform image transfer between VMware servers and image service.


def _start_transfer(context, timeout_secs, read_file_handle, max_data_size,
                    write_file_handle=None, image_service=None, image_id=None,
                    image_meta=None):
    """Start the image transfer.

    The image reader reads the data from the image source and writes to the
    blocking queue. The image source is always a file handle (VmdkReadHandle
    or ImageReadHandle); therefore, a FileReadWriteTask is created for this
    transfer. The image writer reads the data from the blocking queue and
    writes it to the image destination. The image destination is either a
    file or VMDK in VMware datastore or an image in the image service.

    If the destination is a file or VMDK in VMware datastore, the method
    creates a FileReadWriteTask which reads from the blocking queue and
    writes to either FileWriteHandle or VmdkWriteHandle. In the case of
    image service as the destination, an instance of ImageWriter task is
    created which reads from the blocking queue and writes to the image
    service.

    :param context: write context needed for the image service
    :param timeout_secs: time in seconds to wait for the transfer to complete
    :param read_file_handle: handle to read data from
    :param max_data_size: maximum transfer size
    :param write_file_handle: handle to write data to; if this is None, then
                              param image_service  and param image_id should
                              be set.
    :param image_service: image service handle
    :param image_id: ID of the image in the image service
    :param image_meta: image meta-data
    :raises: ImageTransferException, ValueError
    """

    # Create the blocking queue
    blocking_queue = BlockingQueue(BLOCKING_QUEUE_SIZE, max_data_size)

    # Create the image reader
    reader = FileReadWriteTask(read_file_handle, blocking_queue)

    # Create the image writer
    if write_file_handle:
        # File or VMDK in VMware datastore is the image destination
        writer = FileReadWriteTask(blocking_queue, write_file_handle)
    elif image_service and image_id:
        # Image service image is the destination
        writer = ImageWriter(context,
                             blocking_queue,
                             image_service,
                             image_id,
                             image_meta)
    else:
        excep_msg = _("No image destination given.")
        LOG.error(excep_msg)
        raise ValueError(excep_msg)

    # Start the reader and writer
    LOG.debug(_("Starting image transfer with reader: %(reader)s and writer: "
                "%(writer)s"),
              {'reader': reader,
               'writer': writer})
    reader.start()
    writer.start()
    timer = timeout.Timeout(timeout_secs)
    try:
        # Wait for the reader and writer to complete
        reader.wait()
        writer.wait()
    except (timeout.Timeout, exceptions.ImageTransferException) as excep:
        excep_msg = (_("Error occurred during image transfer with reader: "
                       "%(reader)s and writer: %(writer)s") %
                     {'reader': reader,
                      'writer': writer})
        LOG.exception(excep_msg)
        reader.stop()
        writer.stop()

        if isinstance(excep, exceptions.ImageTransferException):
            raise
        raise exceptions.ImageTransferException(excep_msg, excep)
    finally:
        timer.cancel()
        read_file_handle.close()
        if write_file_handle:
            write_file_handle.close()


def download_flat_image(context, timeout_secs, image_service, image_id,
                        **kwargs):
    """Download flat image from the image service to VMware server.

    :param context: image service write context
    :param timeout_secs: time in seconds to wait for the download to complete
    :param image_service: image service handle
    :param image_id: ID of the image to be downloaded
    :param kwargs: keyword arguments to configure the destination
                   file write handle
    :raises: VimConnectionException, ImageTransferException, ValueError
    """
    LOG.debug(_("Downloading image: %s from image service as a flat file."),
              image_id)

    # TODO(vbala) catch specific exceptions raised by download call
    read_iter = image_service.download(context, image_id)
    read_handle = rw_handles.ImageReadHandle(read_iter)
    file_size = int(kwargs.get('image_size'))
    write_handle = rw_handles.FileWriteHandle(kwargs.get('host'),
                                              kwargs.get('data_center_name'),
                                              kwargs.get('datastore_name'),
                                              kwargs.get('cookies'),
                                              kwargs.get('file_path'),
                                              file_size)
    _start_transfer(context,
                    timeout_secs,
                    read_handle,
                    file_size,
                    write_file_handle=write_handle)
    LOG.debug(_("Downloaded image: %s from image service as a flat file."),
              image_id)


def download_stream_optimized_image(context, timeout_secs, image_service,
                                    image_id, **kwargs):
    """Download stream optimized image from image service to VMware server.

    :param context: image service write context
    :param timeout_secs: time in seconds to wait for the download to complete
    :param image_service: image service handle
    :param image_id: ID of the image to be downloaded
    :param kwargs: keyword arguments to configure the destination
                   VMDK write handle
    :returns: managed object reference of the VM created for import to VMware
              server
    :raises: VimException, VimFaultException, VimAttributeException,
             VimSessionOverLoadException, VimConnectionException,
             ImageTransferException, ValueError
    """
    LOG.debug(_("Downloading image: %s from image service as a stream "
                "optimized file."),
              image_id)

    # TODO(vbala) catch specific exceptions raised by download call
    read_iter = image_service.download(context, image_id)
    read_handle = rw_handles.ImageReadHandle(read_iter)
    file_size = int(kwargs.get('image_size'))
    write_handle = rw_handles.VmdkWriteHandle(kwargs.get('session'),
                                              kwargs.get('host'),
                                              kwargs.get('resource_pool'),
                                              kwargs.get('vm_folder'),
                                              kwargs.get('vm_import_spec'),
                                              file_size)
    _start_transfer(context,
                    timeout_secs,
                    read_handle,
                    file_size,
                    write_file_handle=write_handle)
    LOG.debug(_("Downloaded image: %s from image service as a stream "
                "optimized file."),
              image_id)
    return write_handle.get_imported_vm()


def upload_image(context, timeout_secs, image_service, image_id, owner_id,
                 **kwargs):
    """Upload the VM's disk file to image service.

    :param context: image service write context
    :param timeout_secs: time in seconds to wait for the upload to complete
    :param image_service: image service handle
    :param image_id: upload destination image ID
    :param kwargs: keyword arguments to configure the source
                   VMDK read handle
    :raises: VimException, VimFaultException, VimAttributeException,
             VimSessionOverLoadException, VimConnectionException,
             ImageTransferException, ValueError
    """

    LOG.debug(_("Uploading to image: %s."), image_id)
    file_size = kwargs.get('vmdk_size')
    read_handle = rw_handles.VmdkReadHandle(kwargs.get('session'),
                                            kwargs.get('host'),
                                            kwargs.get('vm'),
                                            kwargs.get('vmdk_file_path'),
                                            file_size)

    # Set the image properties. It is important to set the 'size' to 0.
    # Otherwise, the image service client will use the VM's disk capacity
    # which will not be the image size after upload, since it is converted
    # to a stream-optimized sparse disk.
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

    _start_transfer(context,
                    timeout_secs,
                    read_handle,
                    file_size,
                    image_service=image_service,
                    image_id=image_id,
                    image_meta=image_metadata)
    LOG.debug(_("Uploaded image: %s."), image_id)
