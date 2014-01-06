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
Utility classes for image transfer between VMware servers and glance server.
The image transfer uses a LightQueue as a Pipe between the reader and the
writer.
"""

from eventlet import event
from eventlet import greenthread
from eventlet import queue

from openstack.common.gettextutils import _  # noqa
from openstack.common import log as logging
from openstack.common.vmware import exceptions


LOG = logging.getLogger(__name__)


class ThreadSafePipe(queue.LightQueue):
    """The pipe to hold the data which the reader writes to and the writer
    reads from.
    """
    def __init__(self, max_size, max_transfer_size):
        queue.LightQueue.__init__(self, max_size)
        self.max_transfer_size = max_transfer_size
        self.transferred = 0

    def read(self, chunk_size):
        """Read data from the pipe.

        The input chunk size is ignored since we have ensured that the data
        chunks written to the pipe by reader is the same as the chunks asked
        for by writer.
        """
        if self.transferred < self.max_transfer_size:
            data_item = self.get()
            self.transferred += len(data_item)
            LOG.debug(_("Read %(bytes)s out of %(max)s from ThreadSafePipe.") %
                      {'bytes': self.transferred,
                       'max': self.max_transfer_size})
            return data_item
        else:
            LOG.debug(_("Completed transfer of size %s.") % self.transferred)
            return ""

    def write(self, data):
        """Put a data item in the pipe."""
        self.put(data)

    def seek(self, offset, whence=0):
        """Set the file's current position at the offset."""
        pass

    def tell(self):
        """Get size of the file to be read."""
        return self.max_transfer_size

    def close(self):
        """A place-holder to maintain consistency."""
        pass


class GlanceWriteThread(object):
    """Class to write the image data using glance client.

    It also ensures that the image is in the correct ('active') state.
    """

    GLANCE_POLL_INTERVAL = 5

    def __init__(self, context, input_file, image_service, image_id,
                 image_meta=None):
        if not image_meta:
            image_meta = {}

        self.context = context
        self.input_file = input_file
        self.image_service = image_service
        self.image_id = image_id
        self.image_meta = image_meta
        self._running = False

    def start(self):
        self.done = event.Event()

        def _inner():
            """Initiate write thread.

            This method performs image data transfer through an update. After
            the update, it polls the image state until the state becomes
            'active', 'killed' or unknown. ImageTransferException is thrown
            if the final state is not 'active'.
            """
            LOG.debug(_("Initiating image service update on image: %(image)s "
                        "with meta: %(meta)s") % {'image': self.image_id,
                                                  'meta': self.image_meta})
            self.image_service.update(self.context,
                                      self.image_id,
                                      self.image_meta,
                                      data=self.input_file)
            self._running = True
            while self._running:
                try:
                    image_meta = self.image_service.show(self.context,
                                                         self.image_id)
                    image_status = image_meta.get('status')
                    if image_status == 'active':
                        self.stop()
                        LOG.debug(_("Glance image: %s is now active.") %
                                  self.image_id)
                        self.done.send(True)
                    # If the state is killed, then raise an exception.
                    elif image_status == 'killed':
                        self.stop()
                        msg = (_("Glance image: %s is in killed state.") %
                               self.image_id)
                        LOG.error(msg)
                        excep = exceptions.ImageTransferException(msg)
                        self.done.send_exception(excep)
                    elif image_status in ['saving', 'queued']:
                        greenthread.sleep(
                            GlanceWriteThread.GLANCE_POLL_INTERVAL)
                    else:
                        self.stop()
                        msg = _("Glance image %(id)s is in unknown state "
                                "- %(state)s") % {'id': self.image_id,
                                                  'state': image_status}
                        LOG.error(msg)
                        excep = exceptions.ImageTransferException(msg)
                        self.done.send_exception(excep)
                except Exception as exc:
                    LOG.exception(exc)
                    self.stop()
                    self.done.send_exception(exc)

        greenthread.spawn(_inner)
        return self.done

    def stop(self):
        self._running = False

    def wait(self):
        return self.done.wait()

    def close(self):
        pass


class IOThread(object):
    """Class that reads chunks from the input file and writes them to the
    output file till the transfer is completely done.
    """
    IO_THREAD_SLEEP_TIME = 0.01

    def __init__(self, input_file, output_file):
        self.input_file = input_file
        self.output_file = output_file
        self._running = False
        self.got_exception = False

    def start(self):
        self.done = event.Event()

        def _inner():
            """Read data from input and write the same to output."""
            self._running = True
            while self._running:
                try:
                    data = self.input_file.read(None)
                    if not data:
                        self.stop()
                        self.done.send(True)
                    self.output_file.write(data)

                    if hasattr(self.input_file, "update_progress"):
                        self.input_file.update_progress()
                    if hasattr(self.output_file, "update_progress"):
                        self.output_file.update_progress()
                    greenthread.sleep(IOThread.IO_THREAD_SLEEP_TIME)
                except Exception as exc:
                    self.stop()
                    LOG.exception(exc)
                    self.done.send_exception(exc)

        greenthread.spawn(_inner)
        return self.done

    def stop(self):
        self._running = False

    def wait(self):
        return self.done.wait()
