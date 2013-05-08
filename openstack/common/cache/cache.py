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

`cache_backend`: Name of the cache back-end to use.
"""

from oslo.config import cfg
from stevedore import driver

_cache_options = [
    cfg.StrOpt('cache_backend',
               default='memory',
               help='The cache driver to use, default value is `memory`.'),
    cfg.StrOpt('cache_prefix',
               default=None,
               help='Prefix to use in every cache key'),
]


def get_cache(conf):
    """Loads the cache back-end

    This function loads the cache back-end
    specified in the given configuration.

    :param conf: Configuration instance to use
    """
    cache_group = cfg.OptGroup(name='cache',
                               title='Cache options')

    conf.register_group(cache_group)
    conf.register_opts(_cache_options, group=cache_group)

    cache_conf = conf.cache
    kwargs = dict(cache_prefix=cache_conf.cache_prefix)

    # NOTE(flaper87): Load the backend and let it
    # register its configuration options before
    # creating the instance.
    backend = cache_conf.cache_backend
    mgr = driver.DriverManager('openstack.common.cache.backends', backend)
    mgr.driver.register_opts(conf, cache_group)
    return mgr.driver(cache_conf, **kwargs)
