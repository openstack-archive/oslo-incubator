# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# Copyright (c) 2010 Citrix Systems, Inc.
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
Handling of VM disk images.
"""

import os
import re
import tempfile

from oslo.config import cfg

from openstack.common import exception
from openstack.common import fileutils
from openstack.common.gettextutils import _
from openstack.common.image import glance
from openstack.common import log as logging
from openstack.common.processutils import execute_wrapper as execute


LOG = logging.getLogger(__name__)

image_opts = [
    cfg.BoolOpt('force_raw_images',
                default=True,
                help='Force backing images to raw format'),
    cfg.StrOpt('image_conversion_dir',
               default='/tmp',
               help='parent dir for tempdir used for image conversion'),
]

CONF = cfg.CONF
CONF.register_opts(image_opts)


class QemuImgInfo(object):
    BACKING_FILE_RE = re.compile((r"^(.*?)\s*\(actual\s+path\s*:"
                                  r"\s+(.*?)\)\s*$"), re.I)
    TOP_LEVEL_RE = re.compile(r"^([\w\d\s\_\-]+):(.*)$")
    SIZE_RE = re.compile(r"\(\s*(\d+)\s+bytes\s*\)", re.I)

    def __init__(self, cmd_output=None):
        details = self._parse(cmd_output)
        self.image = details.get('image')
        self.backing_file = details.get('backing_file')
        self.file_format = details.get('file_format')
        self.virtual_size = details.get('virtual_size')
        self.cluster_size = details.get('cluster_size')
        self.disk_size = details.get('disk_size')
        self.snapshots = details.get('snapshot_list', [])
        self.encryption = details.get('encryption')

    def __str__(self):
        lines = [
            'image: %s' % self.image,
            'file_format: %s' % self.file_format,
            'virtual_size: %s' % self.virtual_size,
            'disk_size: %s' % self.disk_size,
            'cluster_size: %s' % self.cluster_size,
            'backing_file: %s' % self.backing_file,
        ]
        if self.snapshots:
            lines.append("snapshots: %s" % self.snapshots)
        return "\n".join(lines)

    def _canonicalize(self, field):
        # Standardize on underscores/lc/no dash and no spaces
        # since qemu seems to have mixed outputs here... and
        # this format allows for better integration with python
        # - ie for usage in kwargs and such...
        field = field.lower().strip()
        for c in (" ", "-"):
            field = field.replace(c, '_')
        return field

    def _extract_bytes(self, details):
        # Replace it with the byte amount
        real_size = self.SIZE_RE.search(details)
        if real_size:
            details = real_size.group(1)
        try:
            details = fileutils.to_bytes(details)
        except (TypeError, ValueError):
            pass
        return details

    def _extract_details(self, root_cmd, root_details, lines_after):
        consumed_lines = 0
        real_details = root_details
        if root_cmd == 'backing_file':
            # Replace it with the real backing file
            backing_match = self.BACKING_FILE_RE.match(root_details)
            if backing_match:
                real_details = backing_match.group(2).strip()
        elif root_cmd in ['virtual_size', 'cluster_size', 'disk_size']:
            # Replace it with the byte amount (if we can convert it)
            real_details = self._extract_bytes(root_details)
        elif root_cmd == 'file_format':
            real_details = real_details.strip().lower()
        elif root_cmd == 'snapshot_list':
            # Next line should be a header, starting with 'ID'
            if not lines_after or not lines_after[0].startswith("ID"):
                msg = _("Snapshot list encountered but no header found!")
                raise ValueError(msg)
            consumed_lines += 1
            possible_contents = lines_after[1:]
            real_details = []
            # This is the sprintf pattern we will try to match
            # "%-10s%-20s%7s%20s%15s"
            # ID TAG VM SIZE DATE VM CLOCK (current header)
            for line in possible_contents:
                line_pieces = line.split(None)
                if len(line_pieces) != 6:
                    break
                else:
                    # Check against this pattern in the final position
                    # "%02d:%02d:%02d.%03d"
                    date_pieces = line_pieces[5].split(":")
                    if len(date_pieces) != 3:
                        break
                    real_details.append({
                        'id': line_pieces[0],
                        'tag': line_pieces[1],
                        'vm_size': line_pieces[2],
                        'date': line_pieces[3],
                        'vm_clock': line_pieces[4] + " " + line_pieces[5],
                    })
                    consumed_lines += 1
        return (real_details, consumed_lines)

    def _parse(self, cmd_output):
        # Analysis done of qemu-img.c to figure out what is going on here
        # Find all points start with some chars and then a ':' then a newline
        # and then handle the results of those 'top level' items in a separate
        # function.
        #
        # TODO(harlowja): newer versions might have a json output format
        #                 we should switch to that whenever possible.
        #                 see: http://bit.ly/XLJXDX
        if not cmd_output:
            cmd_output = ''
        contents = {}
        lines = cmd_output.splitlines()
        i = 0
        line_am = len(lines)
        while i < line_am:
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            consumed_lines = 0
            top_level = self.TOP_LEVEL_RE.match(line)
            if top_level:
                root = self._canonicalize(top_level.group(1))
                if not root:
                    i += 1
                    continue
                root_details = top_level.group(2).strip()
                details, consumed_lines = self._extract_details(root,
                                                                root_details,
                                                                lines[i + 1:])
                contents[root] = details
            i += consumed_lines + 1
        return contents


def qemu_img_info(path):
    """Return an object containing the parsed output from qemu-img info."""
    if not os.path.exists(path):
        return QemuImgInfo()

    out, err = execute('env', 'LC_ALL=C', 'LANG=C',
                       'qemu-img', 'info', path)
    return QemuImgInfo(out)


def convert_image(source, dest, out_format, run_as_root=False):
    """Convert image to other format."""
    cmd = ('qemu-img', 'convert', '-O', out_format, source, dest)
    execute(*cmd, run_as_root=run_as_root)


def fetch(context, image_href, path, _user_id, _project_id):
    # TODO(vish): Improve context handling and add owner and auth data
    #             when it is added to glance.  Right now there is no
    #             auth checking in glance, so we assume that access was
    #             checked before we got here.
    (image_service, image_id) = glance.get_remote_image_service(context,
                                                                image_href)
    with fileutils.remove_path_on_error(path):
        with open(path, "wb") as image_file:
            image_service.download(context, image_id, image_file)


def fetch_to_raw(context, image_href, path, user_id, project_id):
    if (CONF.image_conversion_dir and not
            os.path.exists(CONF.image_conversion_dir)):
        os.makedirs(CONF.image_conversion_dir)

    # NOTE(avishay): I'm not crazy about creating temp files which may be
    # large and cause disk full errors which would confuse users.
    # Unfortunately it seems that you can't pipe to 'qemu-img convert' because
    # it seeks. Maybe we can think of something for a future version.
    fd, tmp = tempfile.mkstemp(dir=CONF.image_conversion_dir)
    os.close(fd)

    with fileutils.remove_path_on_error(tmp):
        fetch(context, image_href, tmp, user_id, project_id)

        data = qemu_img_info(tmp)
        fmt = data.file_format
        if fmt is None:
            raise exception.ImageUnacceptable(
                reason=_("'qemu-img info' parsing failed."),
                image_id=image_href)

        backing_file = data.backing_file
        if backing_file is not None:
            raise exception.ImageUnacceptable(
                image_id=image_href,
                reason=_("fmt=%(fmt)s backed by: %(backing_file)s") % locals())

        # NOTE(jdg): I'm using qemu-img convert to write
        # to the volume regardless if it *needs* conversion or not
        # TODO(avishay): We can speed this up by checking if the image is raw
        # and if so, writing directly to the device. However, we need to keep
        # check via 'qemu-img info' that what we copied was in fact a raw
        # image and not a different format with a backing file, which may be
        # malicious.
        if fmt != "raw" and CONF.force_raw_images:
            staged = "%s.converted" % path
            LOG.debug("%s was %s, converting to raw" % (image_href, fmt))
            with fileutils.remove_path_on_error(staged):
                convert_image(tmp, staged, 'raw')
                os.unlink(tmp)

                data = qemu_img_info(staged)
                if data.file_format != "raw":
                    raise exception.ImageUnacceptable(
                        image_id=image_href,
                        reason=_("Converted to raw, but format is now %s") %
                        data.file_format)

                os.rename(staged, path)
        else:
            os.rename(tmp, path)


def upload_volume(context, image_service, image_meta, volume_path):
    image_id = image_meta['id']
    if (image_meta['disk_format'] == 'raw'):
        LOG.debug("%s was raw, no need to convert to %s" %
                  (image_id, image_meta['disk_format']))
        with fileutils.temporary_chown(volume_path):
            with fileutils.file_open(volume_path) as image_file:
                image_service.update(context, image_id, {}, image_file)
        return

    if (CONF.image_conversion_dir and not
            os.path.exists(CONF.image_conversion_dir)):
        os.makedirs(CONF.image_conversion_dir)

    fd, tmp = tempfile.mkstemp(dir=CONF.image_conversion_dir)
    os.close(fd)
    with fileutils.remove_path_on_error(tmp):
        LOG.debug("%s was raw, converting to %s" %
                  (image_id, image_meta['disk_format']))
        convert_image(volume_path, tmp, image_meta['disk_format'])

        data = qemu_img_info(tmp)
        if data.file_format != image_meta['disk_format']:
            raise exception.ImageUnacceptable(
                image_id=image_id,
                reason=_("Converted to %(f1)s, but format is now %(f2)s") %
                {'f1': image_meta['disk_format'], 'f2': data.file_format})

        with fileutils.file_open(tmp) as image_file:
            image_service.update(context, image_id, {}, image_file)
        os.unlink(tmp)
