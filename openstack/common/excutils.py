# Copyright 2011 OpenStack Foundation.
# Copyright 2012, Red Hat, Inc.
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
Exception related utilities.
"""

import logging
import sys
import time
import traceback

import six

from openstack.common.gettextutils import _
from openstack.common.gettextutils import _LE
from openstack.common.gettextutils import _LW
from openstack.common import loopingcall


class save_and_reraise_exception(object):
    """Save current exception, run some code and then re-raise.

    In some cases the exception context can be cleared, resulting in None
    being attempted to be re-raised after an exception handler is run. This
    can happen when eventlet switches greenthreads or when running an
    exception handler, code raises and catches an exception. In both
    cases the exception context will be cleared.

    To work around this, we save the exception state, run handler code, and
    then re-raise the original exception. If another exception occurs, the
    saved exception is logged and the new exception is re-raised.

    In some cases the caller may not want to re-raise the exception, and
    for those circumstances this context provides a reraise flag that
    can be used to suppress the exception.  For example::

      except Exception:
          with save_and_reraise_exception() as ctxt:
              decide_if_need_reraise()
              if not should_be_reraised:
                  ctxt.reraise = False

    If another exception occurs and reraise flag is False,
    the saved exception will not be logged.

    If the caller wants to raise new exception during exception handling
    he/she sets reraise to False initially with an ability to set it back to
    True if needed::

      except Exception:
          with save_and_reraise_exception(reraise=False) as ctxt:
              [if statements to determine whether to raise a new exception]
              # Not raising a new exception, so reraise
              ctxt.reraise = True
    """
    def __init__(self, reraise=True):
        self.reraise = reraise

    def __enter__(self):
        self.type_, self.value, self.tb, = sys.exc_info()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if self.reraise:
                logging.error(_LE('Original exception being dropped: %s'),
                              traceback.format_exception(self.type_,
                                                         self.value,
                                                         self.tb))
            return False
        if self.reraise:
            six.reraise(self.type_, self.value, self.tb)


def forever_retry_uncaught_exceptions(infunc):
    def inner_func(*args, **kwargs):
        last_log_time = 0
        last_exc_message = None
        exc_count = 0
        while True:
            try:
                return infunc(*args, **kwargs)
            except Exception as exc:
                this_exc_message = six.u(str(exc))
                if this_exc_message == last_exc_message:
                    exc_count += 1
                else:
                    exc_count = 1
                # Do not log any more frequently than once a minute unless
                # the exception message changes
                cur_time = int(time.time())
                if (cur_time - last_log_time > 60 or
                        this_exc_message != last_exc_message):
                    logging.exception(
                        _LE('Unexpected exception occurred %d time(s)... '
                            'retrying.') % exc_count)
                    last_log_time = cur_time
                    last_exc_message = this_exc_message
                    exc_count = 0
                # This should be a very rare event. In case it isn't, do
                # a sleep.
                time.sleep(1)
    return inner_func


class RetryDecorator(object):
    """Decorator for retrying a function upon suggested exceptions.

    The decorated function is retried for the given number of times, and the
    sleep time between the retries is incremented until max sleep time is
    reached. If the max retry count is set to -1, then the decorated function
    is invoked indefinitely until an exception is thrown, and the caught
    exception is not in the list of suggested exceptions.
    """

    def __init__(self, max_retry_count=-1, inc_sleep_time=10,
                 max_sleep_time=60, exceptions=()):
        """Configure the retry object using the input params.

        :param max_retry_count: maximum number of times the given function must
                                be retried when one of the input 'exceptions'
                                is caught. When set to -1, it will be retried
                                indefinitely until an exception is thrown
                                and the caught exception is not in param
                                exceptions.
        :param inc_sleep_time: incremental time in seconds for sleep time
                               between retries
        :param max_sleep_time: max sleep time in seconds beyond which the sleep
                               time will not be incremented using param
                               inc_sleep_time. On reaching this threshold,
                               max_sleep_time will be used as the sleep time.
        :param exceptions: suggested exceptions for which the function must be
                           retried
        """
        self._max_retry_count = max_retry_count
        self._inc_sleep_time = inc_sleep_time
        self._max_sleep_time = max_sleep_time
        self._exceptions = exceptions
        self._retry_count = 0
        self._sleep_time = 0

    def __call__(self, f):

        def _func(*args, **kwargs):
            func_name = f.__name__
            try:
                logging.debug(_("Invoking %(func_name)s; retry count is "
                                "%(retry_count)d."),
                              {'func_name': func_name,
                               'retry_count': self._retry_count})
                result = f(*args, **kwargs)
                logging.debug(_("Function %(func_name)s returned successfully "
                                "after %(retry_count)d retries."),
                              {'func_name': func_name,
                               'retry_count': self._retry_count})
            except self._exceptions as excep:
                logging.warn(_LW("Exception which is in the suggested list of "
                                 "exceptions occurred while invoking function:"
                                 " %s."),
                             func_name,
                             exc_info=True)
                if (self._max_retry_count != -1 and
                        self._retry_count >= self._max_retry_count):
                    logging.error(_LE("Cannot retry upon suggested exception "
                                      "since retry count (%(retry_count)d) "
                                      "reached max retry count "
                                      "(%(max_retry_count)d)."),
                                  {'retry_count': self._retry_count,
                                   'max_retry_count': self._max_retry_count})
                    raise excep
                else:
                    self._retry_count += 1
                    self._sleep_time += self._inc_sleep_time
                    return self._sleep_time
            except Exception as excep:
                logging.exception(_LE("Exception which is not in the "
                                      "suggested list of exceptions occurred "
                                      "while invoking %s."),
                                  func_name)
                raise excep
            raise loopingcall.LoopingCallDone(result)

        def func(*args, **kwargs):
            loop = loopingcall.DynamicLoopingCall(_func, *args, **kwargs)
            evt = loop.start(periodic_interval_max=self._max_sleep_time)
            logging.debug(_("Waiting for function %s to return."), f.__name__)
            return evt.wait()

        return func
