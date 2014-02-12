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
Session and API call management for VMware ESX/VC server.

This module contains classes to invoke VIM APIs. It supports
automatic session re-establishment and retry of API invocations
in case of connection problems or server API call overload.
"""

from openstack.common.gettextutils import _
from openstack.common import log as logging
from openstack.common import loopingcall
from openstack.common.vmware import exceptions
from openstack.common.vmware import vim
from openstack.common.vmware import vim_util


LOG = logging.getLogger(__name__)


# TODO(vbala) Move this class to excutils.py.
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
                LOG.debug(_("Invoking %(func_name)s; retry count is "
                            "%(retry_count)d."),
                          {'func_name': func_name,
                           'retry_count': self._retry_count})
                result = f(*args, **kwargs)
                LOG.debug(_("Function %(func_name)s returned successfully "
                            "after %(retry_count)d retries."),
                          {'func_name': func_name,
                           'retry_count': self._retry_count})
            except self._exceptions as excep:
                LOG.warn(_("Exception which is in the suggested list of "
                           "exceptions occurred while invoking function:"
                           " %s."),
                         func_name,
                         exc_info=True)
                if (self._max_retry_count != -1 and
                        self._retry_count >= self._max_retry_count):
                    LOG.error(_("Cannot retry upon suggested exception since "
                                "retry count (%(retry_count)d) reached "
                                "max retry count (%(max_retry_count)d)."),
                              {'retry_count': self._retry_count,
                               'max_retry_count': self._max_retry_count})
                    raise excep
                else:
                    self._retry_count += 1
                    self._sleep_time += self._inc_sleep_time
                    return self._sleep_time
            except Exception as excep:
                LOG.exception(_("Exception which is not in the suggested list "
                                "of exceptions occurred while invoking %s."),
                              func_name)
                raise excep
            raise loopingcall.LoopingCallDone(result)

        def func(*args, **kwargs):
            loop = loopingcall.DynamicLoopingCall(_func, *args, **kwargs)
            evt = loop.start(periodic_interval_max=self._max_sleep_time)
            LOG.debug(_("Waiting for function %s to return."), f.__name__)
            return evt.wait()

        return func


class VMwareAPISession(object):
    """Setup a session with the server and handles all calls made to it.

    Example:
        api_session = VMwareAPISession('10.1.2.3', 'administrator', 'password',
                                       10, 0.1, _create_session=False)
        result = api_session.invoke_api(vim_util, 'get_objects',
                                        api_session.vim, 'HostSystem', 100)
    """

    def __init__(self, host, server_username, server_password,
                 api_retry_count, task_poll_interval, scheme='https',
                 create_session=True, wsdl_loc=None):
        """Initializes the API session with given parameters.

        :param host: ESX/VC server IP address[:port] or host name[:port]
        :param server_username: username of ESX/VC server admin user
        :param server_password: password for param server_username
        :param api_retry_count: number of times an API must be retried upon
                                session/connection related errors
        :param task_poll_interval: sleep time in seconds for polling an
                                   on-going async task as part of the API call
        :param scheme: protocol-- http or https
        :param _create_session: whether to setup a connection at the time of
                               instance creation
        :param wsdl_loc: WSDL file location for invoking SOAP calls on server
                         using suds
        :raises: VimException, VimFaultException, VimAttributeException,
                 VimSessionOverLoadException
        """
        self._host = host
        self._server_username = server_username
        self._server_password = server_password
        self._api_retry_count = api_retry_count
        self._task_poll_interval = task_poll_interval
        self._scheme = scheme
        self._wsdl_loc = wsdl_loc
        self._session_id = None
        self._session_username = None
        self._vim = None
        if create_session:
            self._create_session()

    @property
    def vim(self):
        if not self._vim:
            self._vim = vim.Vim(protocol=self._scheme,
                                host=self._host,
                                wsdl_loc=self._wsdl_loc)
        return self._vim

    @RetryDecorator(exceptions=(exceptions.VimConnectionException,))
    def _create_session(self):
        """Establish session with the server."""
        session_manager = self.vim.service_content.sessionManager
        # Login and create new session with the server for making API calls.
        LOG.debug(_("Logging in with username = %s."), self._server_username)
        session = self.vim.Login(session_manager,
                                 userName=self._server_username,
                                 password=self._server_password)
        prev_session_id, self._session_id = self._session_id, session.key
        # We need to save the username in the session since we may need it
        # later to check active session. The SessionIsActive method requires
        # the username parameter to be exactly same as that in the session
        # object. We can't use the username used for login since the Login
        # method ignores the case.
        self._session_username = session.userName
        LOG.info(_("Successfully established new session; session ID is %s."),
                 self._session_id)

        # Terminate the previous session (if exists) for preserving sessions
        # as there is a limit on the number of sessions we can have.
        if prev_session_id:
            try:
                LOG.info(_("Terminating the previous session with ID = %s"),
                         prev_session_id)
                self.vim.TerminateSession(session_manager,
                                          sessionId=[prev_session_id])
            except Exception:
                # This exception is something we can live with. It is
                # just an extra caution on our side. The session might
                # have been cleared already. We could have made a call to
                # SessionIsActive, but that is an overhead because we
                # anyway would have to call TerminateSession.
                LOG.warn(_("Error occurred while terminating the previous "
                           "session with ID = %s."),
                         prev_session_id,
                         exc_info=True)

    def __del__(self):
        """Log out and terminate the current session."""
        if self._session_id:
            LOG.info(_("Logging out and terminating the current session with "
                       "ID = %s."),
                     self._session_id)
            try:
                self.vim.Logout(self.vim.service_content.sessionManager)
            except Exception:
                LOG.exception(_("Error occurred while logging out and "
                                "terminating the current session with "
                                "ID = %s."),
                              self._session_id)
        else:
            LOG.debug(_("No session exists to log out."))

    def invoke_api(self, module, method, *args, **kwargs):
        """Wrapper method for invoking APIs.

        The API call is retried in the event of exceptions due to session
        overload or connection problems.

        :param module: module corresponding to the VIM API call
        :param method: method in the module which corresponds to the
                       VIM API call
        :param args: arguments to the method
        :param kwargs: keyword arguments to the method
        :returns: response from the API call
        :raises: VimException, VimFaultException, VimAttributeException,
                 VimSessionOverLoadException, VimConnectionException
        """

        @RetryDecorator(max_retry_count=self._api_retry_count,
                        exceptions=(exceptions.VimSessionOverLoadException,
                                    exceptions.VimConnectionException))
        def _invoke_api(module, method, *args, **kwargs):
            LOG.debug(_("Invoking method %(module)s.%(method)s."),
                      {'module': module,
                       'method': method})
            try:
                api_method = getattr(module, method)
                return api_method(*args, **kwargs)
            except exceptions.VimFaultException as excep:
                # If this is due to an inactive session, we should re-create
                # the session and retry.
                if exceptions.NOT_AUTHENTICATED in excep.fault_list:
                    # The NotAuthenticated fault is set by the fault checker
                    # due to an empty response. An empty response could be a
                    # valid response; for e.g., response for the query to
                    # return the VMs in an ESX server which has no VMs in it.
                    # Also, the server responds with an empty response in the
                    # case of an inactive session. Therefore, we need a way to
                    # differentiate between these two cases.
                    if self._is_current_session_active():
                        LOG.debug(_("Returning empty response for "
                                    "%(module)s.%(method)s invocation."),
                                  {'module': module,
                                   'method': method})
                        return []
                    else:
                        # empty response is due to an inactive session
                        excep_msg = (
                            _("Current session: %(session)s is inactive; "
                              "re-creating the session while invoking "
                              "method %(module)s.%(method)s.") %
                            {'session': self._session_id,
                             'module': module,
                             'method': method})
                        LOG.warn(excep_msg, exc_info=True)
                        self._create_session()
                        raise exceptions.VimConnectionException(excep_msg,
                                                                excep)
                else:
                    # no need to retry for other VIM faults like
                    # InvalidArgument
                    # Raise specific exceptions here if possible
                    if excep.fault_list:
                        raise exceptions.get_fault_class(excep.fault_list[0])
                    raise

            except exceptions.VimConnectionException:
                # Re-create the session during connection exception.
                LOG.warn(_("Re-creating session due to connection problems "
                           "while invoking method %(module)s.%(method)s."),
                         {'module': module,
                          'method': method},
                         exc_info=True)
                self._create_session()
                raise

        return _invoke_api(module, method, *args, **kwargs)

    def _is_current_session_active(self):
        """Check if current session is active.

        :returns: True if the session is active; False otherwise
        """
        LOG.debug(_("Checking if the current session: %s is active."),
                  self._session_id)

        is_active = False
        try:
            is_active = self.vim.SessionIsActive(
                self.vim.service_content.sessionManager,
                sessionID=self._session_id,
                userName=self._session_username)
        except exceptions.VimException:
            LOG.warn(_("Error occurred while checking whether the "
                       "current session: %s is active."),
                     self._session_id,
                     exc_info=True)

        return is_active

    def wait_for_task(self, task):
        """Waits for the given task to complete and returns the result.

        The task is polled until it is done. The method returns the task
        information upon successful completion. In case of any error,
        appropriate exception is raised.

        :param task: managed object reference of the task
        :returns: task info upon successful completion of the task
        :raises: VimException, VimFaultException, VimAttributeException,
                 VimSessionOverLoadException, VimConnectionException
        """
        loop = loopingcall.FixedIntervalLoopingCall(self._poll_task, task)
        evt = loop.start(self._task_poll_interval)
        LOG.debug(_("Waiting for the task: %s to complete."), task)
        return evt.wait()

    def _poll_task(self, task):
        """Poll the given task until completion.

        If the task completes successfully, the method returns the task info
        using the input event (param done). In case of any error, appropriate
        exception is set in the event.

        :param task: managed object reference of the task
        """
        LOG.debug(_("Invoking VIM API to read info of task: %s."), task)
        try:
            task_info = self.invoke_api(vim_util,
                                        'get_object_property',
                                        self.vim,
                                        task,
                                        'info')
        except exceptions.VimException as excep:
            LOG.exception(_("Error occurred while reading info of task: %s."),
                          task)
            raise excep
        else:
            if task_info.state in ['queued', 'running']:
                if hasattr(task_info, 'progress'):
                    LOG.debug(_("Task: %(task)s progress is %(progress)s%%."),
                              {'task': task,
                               'progress': task_info.progress})
            elif task_info.state == 'success':
                LOG.debug(_("Task: %s status is success."), task)
                raise loopingcall.LoopingCallDone(task_info)
            else:
                error_msg = unicode(task_info.error.localizedMessage)
                excep_msg = _("Task: %(task)s failed with error: "
                              "%(error)s.") % {'task': task,
                                               'error': error_msg}
                LOG.error(excep_msg)
                error = task_info.error
                name = error.fault.__class__.__name__
                task_ex = exceptions.get_fault_class(name)(error_msg)
                # Check if we can raise a specific exception
                raise task_ex

    def wait_for_lease_ready(self, lease):
        """Waits for the given lease to be ready.

        This method return when the lease is ready. In case of any error,
        appropriate exception is raised.

        :param lease: lease to be checked for
        :raises: VimException, VimFaultException, VimAttributeException,
                 VimSessionOverLoadException, VimConnectionException
        """
        loop = loopingcall.FixedIntervalLoopingCall(self._poll_lease, lease)
        evt = loop.start(self._task_poll_interval)
        LOG.debug(_("Waiting for the lease: %s to be ready."), lease)
        evt.wait()

    def _poll_lease(self, lease):
        """Poll the state of the given lease.

        When the lease is ready, the event (param done) is notified. In case
        of any error, appropriate exception is set in the event.

        :param lease: lease whose state is to be polled
        """
        LOG.debug(_("Invoking VIM API to read state of lease: %s."), lease)
        try:
            state = self.invoke_api(vim_util,
                                    'get_object_property',
                                    self.vim,
                                    lease,
                                    'state')
        except exceptions.VimException as excep:
            LOG.exception(_("Error occurred while checking state of lease: "
                            "%s."),
                          lease)
            raise excep
        else:
            if state == 'ready':
                LOG.debug(_("Lease: %s is ready."), lease)
                raise loopingcall.LoopingCallDone()
            elif state == 'initializing':
                LOG.debug(_("Lease: %s is initializing."), lease)
            elif state == 'error':
                LOG.debug(_("Invoking VIM API to read lease: %s error."),
                          lease)
                error_msg = self._get_error_message(lease)
                excep_msg = _("Lease: %(lease)s is in error state. Details: "
                              "%(error_msg)s.") % {'lease': lease,
                                                   'error_msg': error_msg}
                LOG.error(excep_msg)
                raise exceptions.VimException(excep_msg)
            else:
                # unknown state
                excep_msg = _("Unknown state: %(state)s for lease: "
                              "%(lease)s.") % {'state': state, 'lease': lease}
                LOG.error(excep_msg)
                raise exceptions.VimException(excep_msg)

    def _get_error_message(self, lease):
        """Get error message associated with the given lease."""
        try:
            return self.invoke_api(vim_util,
                                   'get_object_property',
                                   self.vim,
                                   lease,
                                   'error')
        except exceptions.VimException:
            LOG.warn(_("Error occurred while reading error message for lease: "
                       "%s."),
                     lease,
                     exc_info=True)
            return "Unknown"
