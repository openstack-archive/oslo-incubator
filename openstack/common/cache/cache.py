# Copyright 2013 Red Hat, Inc.
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

"""Cache library.

Supported configuration options:

`default_backend`: Name of the cache backend to use.
`key_namespace`: Namespace under which keys will be created.
"""

import urlparse

from stevedore import driver


def register_oslo_configs(conf):
    """Registers a cache configuration options

    :params conf: Config object.
    :type conf: `cfg.ConfigOptions`
    """
    # NOTE(flaper87): Oslo config should be
    # optional. Instead of doing try / except
    # at the top of this file, lets import cfg
    # here and assume that the caller of this
    # function already took care of this dependency.
    from oslo.config import cfg

    _options = [
        cfg.StrOpt('cache_url', default='memory://',
                   help='Url to connect to the cache backend.')
    ]

    conf.register_opts(_options)


def get_cache(url='memory://'):
    """Loads the cache backend

    This function loads the cache backend
    specified in the given configuration.

    :param conf: Configuration instance to use
    """

    parsed = urlparse.urlparse(url)
    backend = parsed.scheme

    kwargs = {}
    if parsed.query:
        # NOTE(flaper87): This returns a dict with
        # key -> [value], those values need to be
        # normalized
        parameters = urlparse.parse_qs(parsed.query)

        for param, value in parameters.items():
            parameters[param] = value[-1]

        kwargs['options'] = parameters

    mgr = driver.DriverManager('openstack.common.cache.backends', backend,
                               invoke_on_load=True,
                               invoke_args=[parsed],
                               invoke_kwds=kwargs)
    return mgr.driver
