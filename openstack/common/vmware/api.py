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
Session and API call management for VMware ESX/VC server.
Provides abstraction over cinder.volume.drivers.vmware.vim.Vim SOAP calls.
"""

from eventlet import event

from openstack.common.gettextutils import _  # noqa
from openstack.common import log as logging
from openstack.common import loopingcall
from openstack.common.vmware import exceptions
from openstack.common.vmware import vim
from openstack.common.vmware import vim_util

LOG = logging.getLogger(__name__)


class Retry(object):
    """Decorator for retrying a function upon suggested exceptions.

    The method retries for the given number of times and the sleep
    time between the retries increments till the max sleep time is
    reached. If max retry count is set to -1, then the decorated
    function is invoked indefinitely until an exception is thrown
    and the caught exception is not in the list of suggested
    exceptions.
    """

    def __init__(self, max_retry_count=-1, inc_sleep_time=10,
                 max_sleep_time=60, exceptions=()):
        """Initialize retry object based on input params.

        :param max_retry_count: Max number of times a function must be
                                retried when one of the input 'exceptions'
                                is caught. When set to -1, it will be retried
                                indefinitely until an exception is thrown
                                and if the caught exception is not in the given
                                list 'exceptions'.
        :param inc_sleep_time: Incremental time in seconds for sleep time
                               between retries
        :param max_sleep_time: Max sleep time in seconds beyond which the sleep
                               time will not be incremented using param
                               inc_sleep_time. On reaching this threshold,
                               max_sleep_time will be used as the sleep time.
        :param exceptions: Suggested exceptions for which the function must be
                           retried
        """
        self._max_retry_count = max_retry_count
        self._inc_sleep_time = inc_sleep_time
        self._max_sleep_time = max_sleep_time
        self._exceptions = exceptions
        self._retry_count = 0
        self._sleep_time = 0

    def __call__(self, f):

        def _func(done, *args, **kwargs):
            try:
                result = f(*args, **kwargs)
                done.send(result)
            except self._exceptions as excep:
                LOG.exception(_("Failure while invoking function: "
                                "%(func)s. Error: %(excep)s."),
                              {'func': f.__name__, 'excep': excep})
                if (self._max_retry_count != -1 and
                        self._retry_count >= self._max_retry_count):
                    done.send_exception(excep)
                else:
                    self._retry_count += 1
                    self._sleep_time += self._inc_sleep_time
                    return self._sleep_time
            except Exception as excep:
                done.send_exception(excep)
            return 0l

        def func(*args, **kwargs):
            done = event.Event()
            loop = loopingcall.DynamicLoopingCall(_func, done, *args, **kwargs)
            loop.start(periodic_interval_max=self._max_sleep_time)
            try:
                result = done.wait()
            finally:
                loop.stop()
            return result

        return func


class VMwareAPISession(object):
    """Setup a session with the server and handles all calls made to it."""

    @Retry(exceptions=(Exception))
    def __init__(self, server_ip, server_username, server_password,
                 api_retry_count, task_poll_interval, scheme='https',
                 create_session=True, wsdl_loc=None):
        """Constructs session object.

        :param server_ip: IP address of ESX/VC server
        :param server_username: Username of ESX/VC server admin user
        :param server_password: Password for param server_username
        :param api_retry_count: Number of times an API must be retried upon
                                session/connection related errors
        :param task_poll_interval: Sleep time in seconds for polling an
                                   on-going async task as part of the API call
        :param scheme: http or https protocol
        :param create_session: Boolean whether to setup connection at the
                               time of instance creation
        :param wsdl_loc: WSDL file location for invoking SOAP calls on server
                         using suds
        """
        self._server_ip = server_ip
        self._server_username = server_username
        self._server_password = server_password
        self._api_retry_count = api_retry_count
        self._task_poll_interval = task_poll_interval
        self._scheme = scheme
        self._wsdl_loc = wsdl_loc
        self._session_id = None
        self._vim = None
        if create_session:
            self.create_session()

    @property
    def vim(self):
        if not self._vim:
            self._vim = vim.Vim(protocol=self._scheme, host=self._server_ip,
                                wsdl_loc=self._wsdl_loc)
        return self._vim

    def create_session(self):
        """Establish session with the server."""
        # Login and setup the session with the server for making API calls
        session_manager = self.vim.service_content.sessionManager
        session = self.vim.Login(session_manager,
                                 userName=self._server_username,
                                 password=self._server_password)
        # Terminate the earlier session, if possible (For the sake of
        # preserving sessions as there is a limit on the number of
        # sessions we can have)
        if self._session_id:
            try:
                self.vim.TerminateSession(session_manager,
                                          sessionId=[self._session_id])
            except Exception as excep:
                # This exception is something we can live with. It is
                # just an extra caution on our side. The session may
                # have been cleared. We could have made a call to
                # SessionIsActive, but that is an overhead because we
                # anyway would have to call TerminateSession.
                LOG.exception(_("Error while terminating session: %s.") %
                              excep)
        self._session_id = session.key
        LOG.info(_("Successfully established connection to the server."))

    def __del__(self):
        """Logs-out the session."""
        try:
            self.vim.Logout(self.vim.service_content.sessionManager)
        except Exception as excep:
            LOG.exception(_("Error while logging out the user: %s.") %
                          excep)

    def invoke_api(self, module, method, *args, **kwargs):
        """Wrapper method for invoking APIs.

        The API call is retried in the event of exceptions due to session
        overload.

        :param module: Module corresponding to the VIM API call
        :param method: Method in the module which corresponds to the
                       VIM API call
        :param args: Arguments to the method
        :param kwargs: Keyword arguments to the method
        :return: Response of the API call
        """

        @Retry(max_retry_count=self._api_retry_count,
               exceptions=(exceptions.VimException))
        def _invoke_api(module, method, *args, **kwargs):
            last_fault_list = []
            while True:
                try:
                    api_method = getattr(module, method)
                    return api_method(*args, **kwargs)
                except exceptions.VimFaultException as excep:
                    if (exceptions.VimFaultException.NOT_AUTHENTICATED not in
                            excep.fault_list):
                        raise excep
                    # If it is a not-authenticated fault, we re-authenticate
                    # the user and retry the API invocation.

                    # There is no way to differentiate an idle session from
                    # a query returning an empty response. This is because
                    # an idle session returns an empty RetrieveProperties
                    # response. If the response is empty after creating a
                    # new session and if the previous response was also an
                    #  empty response, we can be sure that the current empty
                    # response is due to a query returning  empty result.
                    if (exceptions.VimFaultException.NOT_AUTHENTICATED in
                            last_fault_list):
                        return []
                    last_fault_list = excep.fault_list
                    LOG.exception(_("Not authenticated error occurred. "
                                    "Will create session and try "
                                    "API call again: %s.") % excep)
                    self.create_session()

        return _invoke_api(module, method, *args, **kwargs)

    def wait_for_task(self, task):
        """Waits for the given task to complete and returns the result.

        The task is polled until it is done. The method returns the task
        information upon successful completion.

        :param task: Managed object reference of the task
        :return: Task info upon successful completion of the task
        """
        done = event.Event()
        loop = loopingcall.FixedIntervalLoopingCall(self._poll_task,
                                                    task, done)
        loop.start(self._task_poll_interval)
        try:
            task_info = done.wait()
        finally:
            loop.stop()
        return task_info

    def _poll_task(self, task, done):
        """Poll the given task.

        If the task completes successfully, then return the task info.
        In case of error sends back appropriate error.

        :param task: Managed object reference of the task
        :param event: Event that captures task status
        """
        try:
            task_info = self.invoke_api(vim_util, 'get_object_property',
                                        self.vim, task, 'info')
            if task_info.state in ['queued', 'running']:
                # If task has already completed, it will not return
                # the progress.
                if hasattr(task_info, 'progress'):
                    LOG.debug(_("Task: %(task)s progress: %(prog)s.") %
                              {'task': task, 'prog': task_info.progress})
                return
            elif task_info.state == 'success':
                LOG.debug(_("Task: %s status: success.") % task)
                done.send(task_info)
            else:
                error_msg = str(task_info.error.localizedMessage)
                LOG.exception(_("Task: %(task)s failed with error: %(err)s.") %
                              {'task': task, 'err': error_msg})
                done.send_exception(exceptions.VimFaultException([],
                                    error_msg))
        except Exception as excep:
            LOG.exception(_("Task: %(task)s failed with error: %(err)s.") %
                          {'task': task, 'err': excep})
            done.send_exception(excep)

    def wait_for_lease_ready(self, lease):
        """Waits for the given lease to be ready.

        :param task: Lease to be checked for
        """
        done = event.Event()
        loop = loopingcall.FixedIntervalLoopingCall(self._poll_lease,
                                                    lease,
                                                    done)
        loop.start(self._task_poll_interval)
        try:
            done.wait()
        finally:
            loop.stop()

    def _poll_lease(self, lease, done):
        try:
            state = self.invoke_api(vim_util, 'get_object_property',
                                    self.vim, lease, 'state')
            if state == 'ready':
                # done
                LOG.debug(_("Lease is ready."))
                done.send()
                return
            elif state == 'initializing':
                LOG.debug(_("Lease initializing..."))
                return
            elif state == 'error':
                error_msg = self.invoke_api(vim_util, 'get_object_property',
                                            self.vim, lease, 'error')
                LOG.exception(error_msg)
                excep = exceptions.VimFaultException([], error_msg)
                done.send_exception(excep)
            else:
                # unknown state - complain
                error_msg = _("Error: unknown lease state %s.") % state
                raise exceptions.VimFaultException([], error_msg)
        except Exception as excep:
            LOG.exception(excep)
            done.send_exception(excep)
