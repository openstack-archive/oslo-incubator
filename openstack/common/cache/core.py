# -*- coding: utf-8 -*-

# Copyright 2013 Metacloud, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import weakref

from dogpile.cache import api
from dogpile.cache import proxy
from dogpile.cache import region
from dogpile.cache import util as dogpile_util
from oslo.config import cfg
import six

from openstack.common.crypto import utils as crypto
from openstack.common.cache import exceptions
from openstack.common.gettextutils import _
from openstack.common import jsonutils
from openstack.common import log
from openstack.common import importutils


__all__ = ['get_cache_region', 'CacheController', 'NO_VALUE']

BACKENDS_REGISTERED = set()
CACHE_REGION_REGISTRY = weakref.WeakValueDictionary()
CONFIG = cfg.CONF
LOG = log.getLogger(__name__)
NO_VALUE = api.NO_VALUE

CONTROLLER_CONFIG_ARGS = frozenset(['enable_key_mangler', 'key_mangler',
                                    'proxies', 'secret_key',
                                    'secret_strategy'])
REGION_CONFIG_ARGS = frozenset(['backend'])



CONFIG.register_opt(cfg.StrOpt('json_config_file', default=None),
                    group='cache')
CONFIG.register_opt(cfg.ListOpt('dogpile_backends', default=[]), group='cache')


def _register_backends():
    # NOTE(morganfainberg): This function exists to ensure we do not try and
    # register the backends prior to the configuration object being fully
    # available.  We also need to ensure we do not register a given backend
    # more than one time.  All backends will be prefixed with openstack.cache
    # as the "short" name to reference them for configuration purposes.  This
    # function is used in addition to the pre-registered backends for the
    # cache system.

    prefix = 'openstack.cache.%s'
    for backend in CONFIG.cache.dogpile.backends:
        if backend in BACKENDS_REGISTERED:
            continue
        module, cls = backend.rsplit('.', 1)
        backend_name = prefix % cls
        LOG.debug(_('Registering Dogpile Backend %(backend_path)s as '
                    '%(backend_name)s'),
                  {'backend_path': backend, 'backend_name': backend_name})
        region.register_backend(backend_name, module, cls)
        BACKENDS_REGISTERED.add(backend)

def register_oslo_config_options(cc):

    cache_options = [cfg.MultiStrOpt(cc.opt_name('argument'), default=[]),
                     cfg.StrOpt(cc.opt_name('backend')),
                     cfg.BoolOpt(cc.opt_name('enable_key_mangler'),
                                 default=True),
                     cfg.StrOpt(cc.opt_name('key_mangler'),
                                default='dogpile.cache.utils.sha1_mangle_key'),
                     cfg.ListOpt(cc.opt_name('proxies'), default=[]),
                     cfg.StrOpt(cc.opt_name('secret_key'), default=None),
                     cfg.StrOpt(cc.opt_name('security_strategy'),
                                default=None)]

    CONFIG.register_opts(cache_options, group='cache')


class CacheController(object):

    def __init__(self, cache_region):
        self._region = cache_region
        self._crypto = None
        self._security_strategy = None
        self._secret_key = None
        self.cache_on_arguments = self._region.cache_on_arguments
        for opt in CONTROLLER_CONFIG_ARGS:
            # Setup all controller options and set them initially to None
            setattr(self, opt, None)

    def configure(self,
                  ignore_reconfigure=False,
                  function_key_generator=None,
                  function_multi_key_generator=None,
                  **config_arguments):
        """Configure the CacheController instance."""
        # NOTE(morganfainberg): It is a bad idea to reconfigure a backend,
        # there are a lot of pitfalls and edge-cases that could occur.  By far
        # the best approach is to re-create the CacheController object
        # with the new configuration. This will raise RegionAlreadyConfigured
        # if the region has already received configuration.
        try:
            self._assert_not_configured()
        except exceptions.RegionAlreadyConfigured:
            if ignore_reconfigure:
                return
            raise

        config_dict = self._build_config_dict(config_arguments)

        self._configure_controller(**config_dict)
        self._configure_region(**config_dict)
        self.set_key_mangler()
        self.apply_region_proxies()

        region = self._region

        # NOTE(morganfainberg): These key generators are special case functions
        # used by dogpile to actually do the heavy lifting for the key
        # generation. These should only be set if non-default key generation
        # is needed (such as a method to support keyword arguments in
        # for memoizing methods or functions. For the most part these should
        # not be changed.

        if function_key_generator is not None:
            region.function_key_generator = function_key_generator

        if function_multi_key_generator is not None:
            region.function_multi_key_generator = function_multi_key_generator

    @property
    def _config_prefix(self):
        return 'openstack.cache.%s' % self._region.name

    def opt_name(self, opt):
        return '%s_%s' % (self._region.name, opt)

    def _build_config_dict(self, config_args):

        def opt_key(*args):
            return '.'.join(args)

        prefix = self._config_prefix

        if CONFIG.cache.json_config_file is not None:
            # NOTE(morganfainberg): A global configuration file has been set,
            # it is expected this file contains a JSON structure that will
            # give all of the relevant configuration values needed for any
            # and all CacheControllers and Regions. This global configuration
            # file overrides all other configuration options.
            c_data = jsonutils.load(CONFIG.cache.json_config_file)
            if not isinstance(c_data, dict):
                raise exceptions.ConfigurationValidationError(
                    _('Expected dict from json file "%(file)s", got '
                      '"%(type)s".'),
                    {'file': CONFIG.cache.json_config_file,
                     'type': type(c_data)})
        else:
            # NOTE(morganfainberg): No global JSON configuration file has been
            # specified. Build the expected dictionary structure for both the
            # CacheController object and the Dogpile Region.

            def opt_value(opt_name):
                return getattr(CONFIG.cache, self.opt_name(opt_name))

            c_data = {}
            for opt in CONTROLLER_CONFIG_ARGS:
                c_data[opt_key([prefix, opt])] = opt_value(opt)

            for opt in getattr(CONFIG.cache, opt_value('argument')):
                name, value = opt.split('=', 1)
                c_data[opt_key([prefix, 'argument', name])] = value

        # NOTE(morganfainberg): any options explicitly passed into the
        # ``.configure()`` method override all other values.
        for opt in config_args:
            if opt in CONTROLLER_CONFIG_ARGS or opt in REGION_CONFIG_ARGS:
                c_data[opt_key([prefix, opt])] = config_args[opt]
            else:
                c_data[opt_key([prefix, 'argument', opt])] = config_args[opt]

        return c_data

    def _configure_controller(self, **config_arguments):
        """Perform configuration for the CacheController object."""
        prefix = '%s.' % self._config_prefix
        prefix_len = len(prefix)
        for item in config_arguments:
            if item.startswith(prefix):
                arg_name = item[prefix_len:]
                if arg_name in CONTROLLER_CONFIG_ARGS:
                    setattr(self, arg_name, config_arguments[item])
        if self.security_strategy is not None:
            self.security_strategy = self.security_strategy.lower()
            if self.security_strategy not in ['encrypt', 'sign']:
                raise exceptions.ConfigurationValidationError(
                    message=_('Invalid Security Strategy'))
            if self.secret_key is None:
                raise exceptions.ConfigurationValidationError(
                    message=_('Cannot use security_strategy without a '
                              'secret key.'))
            self._crypto = crypto.SymmetricCrypto()

    def _configure_region(self, **config_arguments):
        """Perform the actual dogpile.cache region configuration."""
        prefix = '%s.' % self._config_prefix

        self._region.configure_from_config(config_arguments, prefix)

    def set_key_mangler(self):
        """Set the key_mangler that is appropriate for the given region.

        The key_mangler function is called prior to storing the value(s) in
        the backend.  This is to help prevent collisions and limit issues such
        as memcached's limited cache_key size."""
        if self.enable_key_mangler:
            if (self.security_strategy is not None and
                    self.security_strategy.lower() in ['encrypt', 'sign']):
                global CRYPTO_HASHER
                CRYPTO_HASHER = crypto.HKDF()

                def mangle_hkdf_hex(key):
                    return CRYPTO_HASHER.extract(key, hexdigest=True)

                LOG.info(_('Using crypto HKDF key extraction as key_mangler '
                           'for cache region "%s".'), self._region.name)
                self._region.backend.key_mangler = mangle_hkdf_hex
            elif self.key_mangler is not None:
                key_mangler = importutils.import_class(self.key_mangler)

                if key_mangler is not None:
                    msg = _('Using "%(func)s" as cache region "%(name)s"'
                            ' key_mangler')
                    if callable(key_mangler):
                        self._region.key_mangler = key_mangler
                        LOG.info(msg, {'func': key_mangler.__name__,
                                       'name': self._region.name})
                    else:
                        # NOTE(morganfainberg): We failed to set the key_
                        # mangler, we should error out here to ensure we
                        # aren't causing key-length or collision issues.
                        raise exceptions.ConfigurationValidationError(
                            _('`key_mangler` must be a function reference'))
                else:
                    LOG.info(_('Using default dogpile sha1_mangle_key as '
                               'cache region "%s" key_mangler'),
                             self._region.name)
                    # NOTE(morganfainberg): Sane 'default' keymangler is the
                    # dogpile sha1_mangle_key function.  This ensures
                    # that unless explicitly changed, we mangle keys. This
                    # helps to limit unintended cases of exceeding cache-key
                    # in backends such as memcache.
                    self._region.key_mangler = dogpile_util.sha1_mangle_key
        else:
            LOG.info(_('Cache region "%s" key_mangler disabled.'),
                     self._region.name)

    def apply_region_proxies(self, proxy_list):
        if isinstance(proxy_list, list):
            proxies = []

            for item in proxy_list:
                if isinstance(item, six.string_types):
                    LOG.debug(_('Importing class "%s" as cache region proxy.'),
                              item)
                    pxy = importutils.import_class(item)
                else:
                    pxy = item

                if issubclass(pxy, proxy.ProxyBackend):
                    proxies.append(pxy)
                else:
                    LOG.error(_('"%(proxy)s" is not a '
                                'dogpile.proxy.ProxyBackend: %(type)s'),
                              {'proxy': pxy.__name__, 'type': type(pxy)})

            for proxy_cls in reversed(proxies):
                LOG.info(_('Adding proxy \'%(proxy)s\' to cache region '
                           '%(name)s.'),
                         {'proxy': proxy_cls.__name__,
                          'name': self._region.name})
                self._region.wrap(proxy_cls)

    def _assert_not_configured(self):
        """Convenience method to check region object is not configured."""
        if self.is_configured:
            raise exceptions.RegionAlreadyConfigured(
                region_name=self._region.name)

    def _assert_configured(self):
        """Convenience method to check region object is configured."""
        if not self.is_configured:
            raise exceptions.RegionNotConfigured(region_name=self._region.name)

    @property
    def is_configured(self):
        # NOTE(morganfainberg): In some versions of dogpile.cache the accepted
        # way to check if configuration has occured is to look for 'backend' in
        # the __dict__ (checking to see if the attribute has been set on the
        # instance overriding the inherited attribute).
        return 'backend' in self._region.__dict__

    def _decrypt(self, key, value):
        try:
            value = self._crypto.decrypt(self.secret_key, value,
                                         b64decode=True)
        except Exception as e:
            LOG.error(_('Unable to decrypt data for key "%(key)s": '
                        '%(err)s'),
                      {'key': key, 'err': e})
            raise
        return value

    def _encrypt(self, key, value):
        try:
            value = self._crypto.encrypt(self.secret_key, value,
                                         b64encode=True)
        except Exception as e:
            LOG.error(_('Unable to encrypt data for key "%(key)s": '
                        '%(err)s'),
                      {'key': key, 'err': e})
            raise
        return value

    def get(self, key):
        """Get a single value from the cache region."""
        self._assert_configured()
        value = self._region.get(key)
        if self.security_strategy is not None:
            if self.security_strategy == 'encrypt':
                self._decrypt(key, value)
        return value

    def get_multi(self, keys):
        """Get multiple values in a single call from the cache region."""
        self._assert_configured()
        values = self._region.get_multi(keys)
        if self.security_strategy == 'encrypt':
            for i, value in enumerate(values):
                values[i] = self._decrypt(keys[i], value)
        return values

    def set(self, key, value):
        """Set a single value in the cache region."""
        self._assert_configured()
        if self.security_strategy == 'encrypt':
            value = self._encrypt(key, value)
        self._region.set(key, value)

    def set_multi(self, mapping):
        """Set multiple key/value pairs in the cache region at once.

        :param mapping: dictionary of key/values to store in the cache backend
        """
        self._assert_configured()
        if self.security_strategy == 'encrypt':
            new_mapping = {}
            for k, v in six.iteritems(mapping):
                new_mapping[k] = self._encrypt(k, v)
            mapping = new_mapping
        self._region.set_multi(mapping)

    def delete(self, key):
        """Delete a single key from the cache region."""
        self._assert_configured()
        self._region.delete(key)

    def delete_multi(self, keys):
        """Delete multiple keys from the cache region in a single call."""
        self._assert_configured()
        self._region.delete_multi(keys)

    def invalidate(self):
        """Invalidate this :class:`._region`.

        Invalidation works by setting a current timestamp
        (using ``time.time()``)
        representing the "minimum creation time" for
        a value.  Any retrieved value whose creation
        time is prior to this timestamp
        is considered to be stale.  It does not
        affect the data in the cache in any way, and is also
        local to the instance of :class:`dogpile.cache.region.CacheRegion`.

        See :class:`dogpile.cache.region.CacheRegion.invalidate` for more
        information.
        """
        self._assert_configured()
        self._region.invalidate()


def get_cache_region(name, cache_region=None):
    """Get a new CacheController object referenced by `name`.

    `get_cache_region` returns a CacheController object identified by the
    `name` parameter passed in. If no CacheController object has been created
    with that name, a new (unconfigured) CacheController object is instantiated
    and returned. If a CacheController object was previously created with the
    name passed in, that CacheController object is returned.

    CacheController objects must be configured before use. CacheControllers
    cannot be reconfigured. The underlying registry is a WeakRefValue
    dictionary, meaning that it is possible to create a new CacheController
    object by the same name provided all references to the old CacheController
    object are eliminated.

    Relevant options for each created CacheController object are automatically
    registered.

    Each CacheController requires a 'backend' to be configured and cannot be
    issued a call to .configure() without the backend.

    The CacheController object can be configured in three distinct manners:
        1. A file that contains JSON of the correct format can specified. This
           file will be read in and used as the basis for all CacheController
           object configurations, ignoring the values specified on the
           other registered configuration options.

        2. A number of options for the CacheController object can be configured
           directly in the [cache] section of the configuration file. Each
           option will be automatically created with the name format of
           `<cache_region_name>_<option_name>` (e.g. if a cache region named
           "default_cache" is created the "backend" option would be registered
           as `default_cache_backend`.

        3. Any options passed in (the base name only, e.g. "backend") to the
           `.configure()` method as keyword arguments will supersede any
           arguments configured in the JSON file or the directly-set values
           via the explicitly registered options.

        Options that are registered per backend::

            backend (Str): the dogpile backend to use (e.g.
                           dogpile.cache.Memory). Backend is the only
                           required option.

            enable_key_mangler (Bool): toggle the use of key manglers
                                       for the cache region

            key_mangler (Str): function to use for mangling keys before
                               passing the key to the backend. This is
                               used to ensure consistency in keys and
                               prevent issues with key length
                               limitations such as with memcached
                               (example: "dogpile_util.sha1_mangle_key")

            proxies (ListOpt): A comma-delimited list of dogpile.cache
                               proxy objects to apply to the cache region.
                               dogpile.cache proxies allow for executing
                               code based upon the key, value, or in
                               all occurences in-line before the
                               backend stores the data. This could be used
                               to (for example) compress the data on set
                               operations and decompress data on get
                               operations.

            security_strategy (Str): If set to "encrypt" all `set`
                                     operations will encrypt the data
                                     prior to setting the value (and
                                     before the cache region or proxies
                                     see the data).  `get` operations
                                     will decrypt the data.

                                     If set to "sign" all `set`
                                     operations will produce a signed
                                     data blob of the value (and pass
                                     that to the cache region and
                                     proxies). `get` operations will
                                     validate this signature before
                                     returning data.

                                     If security_strategy is configured a
                                     cryptographically secure key_mangler
                                     is used in lieu of any other
                                     key_mangler configured unless
                                     `enable_key_mangler` is set to false.

                                     This option requires `secret_key`
                                     to also be set.

            secret_key (Str): The encryption key used for signing or
                              symmetrical encryption when
                              `security_strategy` is configured.

            argument (MultiStr): Each definition of the "argument" option
                                 will have the value split on the first '='
                                 and will pass that key/value to the
                                 dogpile.cache driver. Many drivers have
                                 explicit argument requirements and
                                 this allows these arbitrary arguments to
                                 be passed to the backend. The split on
                                 '=' will only be done for use in the
                                 oslo-based configuration file.

                                 For use in the JSON configuration file
                                 the key is
                                 `openstack.cache.<region_name>.argument.<arg>`

                                 For overrides via the keyword arguments
                                 passed to `.configure()` simply use the
                                 arg name as the key (e.g. 'servers'), this
                                 name will be transformed into the appropriate
                                 `openstack.cache.<region_name>.argument.<arg>`
                                 format automatically.

    Example `get_cache_region` and configuration::

        >>> from openstack.common import cache
        >>> region = cache.get_cache_region('default')
        >>> region.configure(backend='dogpile.cache.Memory',
        ...                  key_mangler='dogpile_util.sha1_mangle_key',
        ...                  enable_key_mangler=True,
        ...                  security_strategy='encrypt',
        ...                  secret_key='VerySecureKey')
        ...
        >>> region.set('user-bob-key', {'user_name': 'bob',
        ...                             'user_id': 12345})
        ...
        >>> region.get('user-bob-key')
        ... {'user_name': 'bob', 'user_id': 12345})
        ...
        >>> region.delete('user-bob-key')
        >>> region.get('user-bob-key')
        ... <dogpile.cache.api.NoValue object at 0x10abd8910>

        ..NOTE::
            `dogpile.cache` will return a special object called NO_VALUE that
            is a singleton if a value doesn't exist. This object can be found
            at `openstack.common.cache.NO_VALUE`. The NO_VALUE object evaluates
            to a boolean False the same as an empty dictionary or list would.

    :param name: name of the Cache Regions, multiple calls to get_cache_region
                 with the same name will return the same CacheController obj
    :param cache_region: optional dogpile.cache region object to use as the
                         backend for the new CacheController object
    """
    _register_backends()
    cache_controller = CACHE_REGION_REGISTRY.get(name)
    if cache_controller is None:
        if cache_region is None:
            cache_region = region.make_region(name=name)
        cache_controller = CacheController(cache_region)
        register_oslo_config_options(cache_controller)
        CACHE_REGION_REGISTRY[name] = cache_controller
    return cache_controller
