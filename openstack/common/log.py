# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack Foundation.
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""Openstack logging handler.

This module adds to logging functionality by adding the option to specify
a context object when calling the various log methods.  If the context object
is not specified, default formatting is used. Additionally, an instance uuid
may be passed as part of the log message, which is intended to make it easier
for admins to find messages related to a specific instance.

It also allows setting of formatting information through conf.

"""

import ConfigParser
import cStringIO
import inspect
import itertools
import logging
import logging.config
import logging.handlers
import os
import stat
import sys
import traceback

from oslo.config import cfg

from openstack.common.gettextutils import _
from openstack.common import jsonutils
from openstack.common import local
from openstack.common import notifier


_DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)8s [%(name)s] %(message)s"
_DEFAULT_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

common_cli_opts = [
    cfg.BoolOpt('debug',
                short='d',
                default=False,
                help='Print debugging output (set logging level to '
                     'DEBUG instead of default WARNING level).'),
    cfg.BoolOpt('verbose',
                short='v',
                default=False,
                help='Print more verbose output (set logging level to '
                     'INFO instead of default WARNING level).'),
]

logging_cli_opts = [
    cfg.StrOpt('log-config',
               metavar='PATH',
               help='If this option is specified, the logging configuration '
                    'file specified is used and overrides any other logging '
                    'options specified. Please see the Python logging module '
                    'documentation for details on logging configuration '
                    'files.'),
    cfg.StrOpt('log-format',
               default=_DEFAULT_LOG_FORMAT,
               metavar='FORMAT',
               help='A logging.Formatter log message format string which may '
                    'use any of the available logging.LogRecord attributes. '
                    'Default: %(default)s'),
    cfg.StrOpt('log-date-format',
               default=_DEFAULT_LOG_DATE_FORMAT,
               metavar='DATE_FORMAT',
               help='Format string for %%(asctime)s in log records. '
                    'Default: %(default)s'),
    cfg.StrOpt('log-file',
               metavar='PATH',
               deprecated_name='logfile',
               help='(Optional) Name of log file to output to. '
                    'If no default is set, logging will go to stdout.'),
    cfg.StrOpt('log-dir',
               deprecated_name='logdir',
               help='(Optional) The base directory used for relative '
                    '--log-file paths'),
    cfg.BoolOpt('use-syslog',
                default=False,
                help='Use syslog for logging.'),
    cfg.StrOpt('syslog-log-facility',
               default='LOG_USER',
               help='syslog facility to receive log lines')
]

generic_log_opts = [
    cfg.BoolOpt('use_stderr',
                default=True,
                help='Log output to standard error'),
    cfg.StrOpt('logfile_mode',
               default='0644',
               help='Default file mode used when creating log files'),
]

log_opts = [
    cfg.StrOpt('logging_context_format_string',
               default='%(asctime)s.%(msecs)03d %(process)d %(levelname)s '
                       '%(name)s [%(request_id)s %(user)s %(tenant)s] '
                       '%(instance)s%(message)s',
               help='format string to use for log messages with context'),
    cfg.StrOpt('logging_default_format_string',
               default='%(asctime)s.%(msecs)03d %(process)d %(levelname)s '
                       '%(name)s [-] %(instance)s%(message)s',
               help='format string to use for log messages without context'),
    cfg.StrOpt('logging_debug_format_suffix',
               default='%(funcName)s %(pathname)s:%(lineno)d',
               help='data to append to log format when level is DEBUG'),
    cfg.StrOpt('logging_exception_prefix',
               default='%(asctime)s.%(msecs)03d %(process)d TRACE %(name)s '
               '%(instance)s',
               help='prefix each line of exception output with this format'),
    cfg.ListOpt('default_log_levels',
                default=[
                    'amqplib=WARN',
                    'sqlalchemy=WARN',
                    'boto=WARN',
                    'suds=INFO',
                    'keystone=INFO',
                    'eventlet.wsgi.server=WARN'
                ],
                help='list of logger=LEVEL pairs'),
    cfg.BoolOpt('publish_errors',
                default=False,
                help='publish error events'),
    cfg.BoolOpt('fatal_deprecations',
                default=False,
                help='make deprecations fatal'),

    # NOTE(mikal): there are two options here because sometimes we are handed
    # a full instance (and could include more information), and other times we
    # are just handed a UUID for the instance.
    cfg.StrOpt('instance_format',
               default='[instance: %(uuid)s] ',
               help='If an instance is passed with the log message, format '
                    'it like this'),
    cfg.StrOpt('instance_uuid_format',
               default='[instance: %(uuid)s] ',
               help='If an instance UUID is passed with the log message, '
                    'format it like this'),
]

CONF = cfg.CONF
CONF.register_cli_opts(common_cli_opts)
CONF.register_cli_opts(logging_cli_opts)
CONF.register_opts(generic_log_opts)
CONF.register_opts(log_opts)

# our new audit level
# NOTE(jkoelker) Since we synthesized an audit level, make the logging
#                module aware of it so it acts like other levels.
logging.AUDIT = logging.INFO + 1
logging.addLevelName(logging.AUDIT, 'AUDIT')


try:
    NullHandler = logging.NullHandler
except AttributeError:  # NOTE(jkoelker) NullHandler added in Python 2.7
    class NullHandler(logging.Handler):
        def handle(self, record):
            pass

        def emit(self, record):
            pass

        def createLock(self):
            self.lock = None


def _dictify_context(context):
    if context is None:
        return None
    if not isinstance(context, dict) and getattr(context, 'to_dict', None):
        context = context.to_dict()
    return context


def _get_binary_name():
    return os.path.basename(inspect.stack()[-1][1])


def _get_log_file_path(binary=None):
    logfile = CONF.log_file
    logdir = CONF.log_dir

    if logfile and not logdir:
        return logfile

    if logfile and logdir:
        return os.path.join(logdir, logfile)

    if logdir:
        binary = binary or _get_binary_name()
        return '%s.log' % (os.path.join(logdir, binary),)


class BaseLoggerAdapter(logging.LoggerAdapter):

    def audit(self, msg, *args, **kwargs):
        self.log(logging.AUDIT, msg, *args, **kwargs)


class LazyAdapter(BaseLoggerAdapter):
    def __init__(self, name='unknown', version='unknown'):
        self._logger = None
        self.extra = {}
        self.name = name
        self.version = version

    @property
    def logger(self):
        if not self._logger:
            self._logger = getLogger(self.name, self.version)
        return self._logger


class ContextAdapter(BaseLoggerAdapter):
    warn = logging.LoggerAdapter.warning

    def __init__(self, logger, project_name, version_string):
        self.logger = logger
        self.project = project_name
        self.version = version_string

    @property
    def handlers(self):
        return self.logger.handlers

    def deprecated(self, msg, *args, **kwargs):
        stdmsg = _("Deprecated: %s") % msg
        if CONF.fatal_deprecations:
            self.critical(stdmsg, *args, **kwargs)
            raise DeprecatedConfig(msg=stdmsg)
        else:
            self.warn(stdmsg, *args, **kwargs)

    def process(self, msg, kwargs):
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        extra = kwargs['extra']

        context = kwargs.pop('context', None)
        if not context:
            context = getattr(local.store, 'context', None)
        if context:
            extra.update(_dictify_context(context))

        instance = kwargs.pop('instance', None)
        instance_extra = ''
        if instance:
            instance_extra = CONF.instance_format % instance
        else:
            instance_uuid = kwargs.pop('instance_uuid', None)
            if instance_uuid:
                instance_extra = (CONF.instance_uuid_format
                                  % {'uuid': instance_uuid})
        extra.update({'instance': instance_extra})

        extra.update({"project": self.project})
        extra.update({"version": self.version})
        extra['extra'] = extra.copy()
        return msg, kwargs


class JSONFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None):
        # NOTE(jkoelker) we ignore the fmt argument, but its still there
        #                since logging.config.fileConfig passes it.
        self.datefmt = datefmt

    def formatException(self, ei, strip_newlines=True):
        lines = traceback.format_exception(*ei)
        if strip_newlines:
            lines = [itertools.ifilter(
                lambda x: x,
                line.rstrip().splitlines()) for line in lines]
            lines = list(itertools.chain(*lines))
        return lines

    def format(self, record):
        message = {'message': record.getMessage(),
                   'asctime': self.formatTime(record, self.datefmt),
                   'name': record.name,
                   'msg': record.msg,
                   'args': record.args,
                   'levelname': record.levelname,
                   'levelno': record.levelno,
                   'pathname': record.pathname,
                   'filename': record.filename,
                   'module': record.module,
                   'lineno': record.lineno,
                   'funcname': record.funcName,
                   'created': record.created,
                   'msecs': record.msecs,
                   'relative_created': record.relativeCreated,
                   'thread': record.thread,
                   'thread_name': record.threadName,
                   'process_name': record.processName,
                   'process': record.process,
                   'traceback': None}

        if hasattr(record, 'extra'):
            message['extra'] = record.extra

        if record.exc_info:
            message['traceback'] = self.formatException(record.exc_info)

        return jsonutils.dumps(message)


class PublishErrorsHandler(logging.Handler):
    def emit(self, record):
        if ('openstack.common.notifier.log_notifier' in
                CONF.notification_driver):
            return
        notifier.api.notify(None, 'error.publisher',
                            'error_notification',
                            notifier.api.ERROR,
                            dict(error=record.msg))


def _create_logging_excepthook(product_name):
    def logging_excepthook(type, value, tb):
        extra = {}
        if CONF.verbose:
            extra['exc_info'] = (type, value, tb)
        getLogger(product_name).critical(str(value), **extra)
    return logging_excepthook


class LogConfigError(Exception):

    message = _('Error loading logging config %(log_config)s: %(err_msg)s')

    def __init__(self, log_config, err_msg):
        self.log_config = log_config
        self.err_msg = err_msg

    def __str__(self):
        return self.message % dict(log_config=self.log_config,
                                   err_msg=self.err_msg)


def _load_log_config(log_config):
    try:
        logging.config.fileConfig(log_config)
    except ConfigParser.Error, exc:
        raise LogConfigError(log_config, str(exc))


def setup(product_name):
    """Setup logging."""
    if CONF.log_config:
        _load_log_config(CONF.log_config)
    else:
        _setup_logging_from_conf()
    sys.excepthook = _create_logging_excepthook(product_name)


def set_defaults(logging_context_format_string):
    cfg.set_defaults(log_opts,
                     logging_context_format_string=
                     logging_context_format_string)


def _find_facility_from_conf():
    facility_names = logging.handlers.SysLogHandler.facility_names
    facility = getattr(logging.handlers.SysLogHandler,
                       CONF.syslog_log_facility,
                       None)

    if facility is None and CONF.syslog_log_facility in facility_names:
        facility = facility_names.get(CONF.syslog_log_facility)

    if facility is None:
        valid_facilities = facility_names.keys()
        consts = ['LOG_AUTH', 'LOG_AUTHPRIV', 'LOG_CRON', 'LOG_DAEMON',
                  'LOG_FTP', 'LOG_KERN', 'LOG_LPR', 'LOG_MAIL', 'LOG_NEWS',
                  'LOG_AUTH', 'LOG_SYSLOG', 'LOG_USER', 'LOG_UUCP',
                  'LOG_LOCAL0', 'LOG_LOCAL1', 'LOG_LOCAL2', 'LOG_LOCAL3',
                  'LOG_LOCAL4', 'LOG_LOCAL5', 'LOG_LOCAL6', 'LOG_LOCAL7']
        valid_facilities.extend(consts)
        raise TypeError(_('syslog facility must be one of: %s') %
                        ', '.join("'%s'" % fac
                                  for fac in valid_facilities))

    return facility


def _setup_logging_from_conf():
    log_root = getLogger(None).logger
    for handler in log_root.handlers:
        log_root.removeHandler(handler)

    if CONF.use_syslog:
        facility = _find_facility_from_conf()
        syslog = logging.handlers.SysLogHandler(address='/dev/log',
                                                facility=facility)
        log_root.addHandler(syslog)

    logpath = _get_log_file_path()
    if logpath:
        filelog = logging.handlers.WatchedFileHandler(logpath)
        log_root.addHandler(filelog)

        mode = int(CONF.logfile_mode, 8)
        st = os.stat(logpath)
        if st.st_mode != (stat.S_IFREG | mode):
            os.chmod(logpath, mode)

    if CONF.use_stderr:
        streamlog = ColorHandler()
        log_root.addHandler(streamlog)

    elif not CONF.log_file:
        # pass sys.stdout as a positional argument
        # python2.6 calls the argument strm, in 2.7 it's stream
        streamlog = logging.StreamHandler(sys.stdout)
        log_root.addHandler(streamlog)

    if CONF.publish_errors:
        log_root.addHandler(PublishErrorsHandler(logging.ERROR))

    for handler in log_root.handlers:
        datefmt = CONF.log_date_format
        if CONF.log_format:
            handler.setFormatter(logging.Formatter(fmt=CONF.log_format,
                                                   datefmt=datefmt))
        else:
            handler.setFormatter(LegacyFormatter(datefmt=datefmt))

    if CONF.debug:
        log_root.setLevel(logging.DEBUG)
    elif CONF.verbose:
        log_root.setLevel(logging.INFO)
    else:
        log_root.setLevel(logging.WARNING)

    level = logging.NOTSET
    for pair in CONF.default_log_levels:
        mod, _sep, level_name = pair.partition('=')
        level = logging.getLevelName(level_name)
        logger = logging.getLogger(mod)
        logger.setLevel(level)
        for handler in log_root.handlers:
            logger.addHandler(handler)

_loggers = {}


def getLogger(name='unknown', version='unknown'):
    if name not in _loggers:
        _loggers[name] = ContextAdapter(logging.getLogger(name),
                                        name,
                                        version)
    return _loggers[name]


def getLazyLogger(name='unknown', version='unknown'):
    """
    create a pass-through logger that does not create the real logger
    until it is really needed and delegates all calls to the real logger
    once it is created
    """
    return LazyAdapter(name, version)


class WritableLogger(object):
    """A thin wrapper that responds to `write` and logs."""

    def __init__(self, logger, level=logging.INFO):
        self.logger = logger
        self.level = level

    def write(self, msg):
        self.logger.log(self.level, msg)


class LegacyFormatter(logging.Formatter):
    """A context.RequestContext aware formatter configured through flags.

    The flags used to set format strings are: logging_context_format_string
    and logging_default_format_string.  You can also specify
    logging_debug_format_suffix to append extra formatting if the log level is
    debug.

    For information about what variables are available for the formatter see:
    http://docs.python.org/library/logging.html#formatter

    """

    def format(self, record):
        """Uses contextstring if request_id is set, otherwise default."""
        # NOTE(sdague): default the fancier formating params
        # to an empty string so we don't throw an exception if
        # they get used
        for key in ('instance', 'color'):
            if key not in record.__dict__:
                record.__dict__[key] = ''

        if record.__dict__.get('request_id', None):
            self._fmt = CONF.logging_context_format_string
        else:
            self._fmt = CONF.logging_default_format_string

        if (record.levelno == logging.DEBUG and
                CONF.logging_debug_format_suffix):
            self._fmt += " " + CONF.logging_debug_format_suffix

        # Cache this on the record, Logger will respect our formated copy
        if record.exc_info:
            record.exc_text = self.formatException(record.exc_info, record)
        return logging.Formatter.format(self, record)

    def formatException(self, exc_info, record=None):
        """Format exception output with CONF.logging_exception_prefix."""
        if not record:
            return logging.Formatter.formatException(self, exc_info)

        stringbuffer = cStringIO.StringIO()
        traceback.print_exception(exc_info[0], exc_info[1], exc_info[2],
                                  None, stringbuffer)
        lines = stringbuffer.getvalue().split('\n')
        stringbuffer.close()

        if CONF.logging_exception_prefix.find('%(asctime)') != -1:
            record.asctime = self.formatTime(record, self.datefmt)

        formatted_lines = []
        for line in lines:
            pl = CONF.logging_exception_prefix % record.__dict__
            fl = '%s%s' % (pl, line)
            formatted_lines.append(fl)
        return '\n'.join(formatted_lines)


class ColorHandler(logging.StreamHandler):
    LEVEL_COLORS = {
        logging.DEBUG: '\033[00;32m',  # GREEN
        logging.INFO: '\033[00;36m',  # CYAN
        logging.AUDIT: '\033[01;36m',  # BOLD CYAN
        logging.WARN: '\033[01;33m',  # BOLD YELLOW
        logging.ERROR: '\033[01;31m',  # BOLD RED
        logging.CRITICAL: '\033[01;31m',  # BOLD RED
    }

    def format(self, record):
        record.color = self.LEVEL_COLORS[record.levelno]
        return logging.StreamHandler.format(self, record)


class DeprecatedConfig(Exception):
    message = _("Fatal call to deprecated config: %(msg)s")

    def __init__(self, msg):
        super(Exception, self).__init__(self.message % dict(msg=msg))
