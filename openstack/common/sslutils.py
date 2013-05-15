# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 IBM Corp.
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

import os
import ssl

from oslo.config import cfg

from openstack.common.gettextutils import _


ssl_opts = [
    cfg.StrOpt('ca_file',
               default=None,
               help="CA certificate file to use to verify "
                    "connecting clients"),
    cfg.StrOpt('cert_file',
               default=None,
               help="Certificate file to use when starting "
                    "the server securely"),
    cfg.StrOpt('key_file',
               default=None,
               help="Private key file to use when starting "
                    "the server securely"),
]


CONF = cfg.CONF
CONF.register_opts(ssl_opts, "ssl")


class SslWrapper(object):
    def __init__(self, opts=None):
        if opts is None:
            opts = {}

        self.cert_file = self._getopt('cert_file', opts)
        self.key_file = self._getopt('key_file', opts)
        self.ca_file = self._getopt('ca_file', opts)
        self.use_ssl = (opts.get('use_ssl', True) and
                        (self.cert_file or self.key_file))

        if self.use_ssl:
            if not self.cert_file or not self.key_file:
                raise RuntimeError(_("When running server in SSL mode, you "
                                     "must specify both a cert_file and "
                                     "key_file option value in your "
                                     "configuration file."))

    @property
    def enabled(self):
        return self.use_ssl

    def _file_exists(self, filename):
        return os.path.exists(filename)

    def _getopt(self, key, opts):
        value = opts.get(key, None)
        if value is None:
            value = getattr(CONF.ssl, key)

        if value is not None and not self._file_exists(value):
            raise RuntimeError(_("Unable to find %(key)s : %(value)s") %
                               {'key': key, 'value': value})

        return value

    def wrap(self, sock):
        ssl_kwargs = {
            'server_side': True,
            'certfile': self.cert_file,
            'keyfile': self.key_file,
            'cert_reqs': ssl.CERT_NONE,
        }

        if self.ca_file:
            ssl_kwargs['ca_certs'] = self.ca_file
            ssl_kwargs['cert_reqs'] = ssl.CERT_REQUIRED

        return ssl.wrap_socket(sock, **ssl_kwargs)
