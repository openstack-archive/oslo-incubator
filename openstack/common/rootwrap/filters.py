# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 OpenStack Foundation.
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

import os
import re


class CommandFilter(object):
    """Command filter only checking that the 1st argument matches exec_path."""

    def __init__(self, exec_path, run_as, *args):
        self.name = ''
        self.exec_path = exec_path
        self.run_as = run_as
        self.args = args
        self.real_exec = None

    def get_exec(self, exec_dirs=[]):
        """Returns existing executable, or empty string if none found."""
        if self.real_exec is not None:
            return self.real_exec
        self.real_exec = ""
        if self.exec_path.startswith('/'):
            if os.access(self.exec_path, os.X_OK):
                self.real_exec = self.exec_path
        else:
            for binary_path in exec_dirs:
                expanded_path = os.path.join(binary_path, self.exec_path)
                if os.access(expanded_path, os.X_OK):
                    self.real_exec = expanded_path
                    break
        return self.real_exec

    def match(self, userargs):
        """Only check that the first argument (command) matches exec_path."""
        return os.path.basename(self.exec_path) == userargs[0]

    def get_command(self, userargs, exec_dirs=[]):
        """Returns command to execute (with sudo -u if run_as != root)."""
        to_exec = self.get_exec(exec_dirs=exec_dirs) or self.exec_path
        if (self.run_as != 'root'):
            # Used to run commands at lesser privileges
            return ['sudo', '-u', self.run_as, to_exec] + userargs[1:]
        return [to_exec] + userargs[1:]

    def get_environment(self, userargs):
        """Returns specific environment to set, None if none."""
        return None


class RegExpFilter(CommandFilter):
    """Command filter doing regexp matching for every argument."""

    def match(self, userargs):
        # Early skip if command or number of args don't match
        if (len(self.args) != len(userargs)):
            # DENY: argument numbers don't match
            return False
        # Compare each arg (anchoring pattern explicitly at end of string)
        for (pattern, arg) in zip(self.args, userargs):
            try:
                if not re.match(pattern + '$', arg):
                    break
            except re.error:
                # DENY: Badly-formed filter
                return False
        else:
            # ALLOW: All arguments matched
            return True

        # DENY: Some arguments did not match
        return False


class PathFilter(CommandFilter):
    """Command filter checking that path arguments are within given dirs

        One can specify the following constraints for command arguments:
            1) pass     - pass an argument as is to the resulting command
            2) some_str - check if an argument is equal to the given string
            3) abs path - check if a path argument is within the given base dir

        A typical rootwrapper filter entry looks like this:
            # cmdname: filter name, raw command, user, arg_i_constraint [, ...]
            chown: PathFilter, /bin/chown, root, nova, /var/lib/images

    """

    def match(self, userargs):
        command, arguments = userargs[0], userargs[1:]

        equal_args_num = len(self.args) == len(arguments)
        exec_is_valid = super(PathFilter, self).match(userargs)
        args_equal_or_pass = all(
            arg == 'pass' or arg == value
            for arg, value in zip(self.args, arguments)
            if not os.path.isabs(arg)  # arguments not specifying abs paths
        )
        paths_are_within_base_dirs = all(
            os.path.commonprefix([arg, os.path.realpath(value)]) == arg
            for arg, value in zip(self.args, arguments)
            if os.path.isabs(arg)  # arguments specifying abs paths
        )

        return (equal_args_num and
                exec_is_valid and
                args_equal_or_pass and
                paths_are_within_base_dirs)

    def get_command(self, userargs, exec_dirs=[]):
        command, arguments = userargs[0], userargs[1:]

        # convert path values to canonical ones; copy other args as is
        args = [os.path.realpath(value) if os.path.isabs(arg) else value
                for arg, value in zip(self.args, arguments)]

        return super(PathFilter, self).get_command([command] + args,
                                                   exec_dirs)


class DnsmasqFilter(CommandFilter):
    """Specific filter for the dnsmasq call (which includes env)."""

    CONFIG_FILE_ARG = 'CONFIG_FILE'

    def match(self, userargs):
        if (userargs[0] == 'env' and
                userargs[1].startswith(self.CONFIG_FILE_ARG) and
                userargs[2].startswith('NETWORK_ID=') and
                userargs[3] == 'dnsmasq'):
            return True
        return False

    def get_command(self, userargs, exec_dirs=[]):
        to_exec = self.get_exec(exec_dirs=exec_dirs) or self.exec_path
        dnsmasq_pos = userargs.index('dnsmasq')
        return [to_exec] + userargs[dnsmasq_pos + 1:]

    def get_environment(self, userargs):
        env = os.environ.copy()
        env[self.CONFIG_FILE_ARG] = userargs[1].split('=')[-1]
        env['NETWORK_ID'] = userargs[2].split('=')[-1]
        return env


class DeprecatedDnsmasqFilter(DnsmasqFilter):
    """Variant of dnsmasq filter to support old-style FLAGFILE."""
    CONFIG_FILE_ARG = 'FLAGFILE'


class KillFilter(CommandFilter):
    """Specific filter for the kill calls.
       1st argument is the user to run /bin/kill under
       2nd argument is the location of the affected executable
       Subsequent arguments list the accepted signals (if any)

       This filter relies on /proc to accurately determine affected
       executable, so it will only work on procfs-capable systems (not OSX).
    """

    def __init__(self, *args):
        super(KillFilter, self).__init__("/bin/kill", *args)

    def match(self, userargs):
        if userargs[0] != "kill":
            return False
        args = list(userargs)
        if len(args) == 3:
            # A specific signal is requested
            signal = args.pop(1)
            if signal not in self.args[1:]:
                # Requested signal not in accepted list
                return False
        else:
            if len(args) != 2:
                # Incorrect number of arguments
                return False
            if len(self.args) > 1:
                # No signal requested, but filter requires specific signal
                return False
        try:
            command = os.readlink("/proc/%d/exe" % int(args[1]))
            # NOTE(yufang521247): /proc/PID/exe may have '\0' on the
            # end, because python doen't stop at '\0' when read the
            # target path.
            command = command.split('\0')[0]
            # NOTE(dprince): /proc/PID/exe may have ' (deleted)' on
            # the end if an executable is updated or deleted
            if command.endswith(" (deleted)"):
                command = command[:command.rindex(" ")]
            if command != self.args[0]:
                # Affected executable does not match
                return False
        except (ValueError, OSError):
            # Incorrect PID
            return False
        return True


class ReadFileFilter(CommandFilter):
    """Specific filter for the utils.read_file_as_root call."""

    def __init__(self, file_path, *args):
        self.file_path = file_path
        super(ReadFileFilter, self).__init__("/bin/cat", "root", *args)

    def match(self, userargs):
        if userargs[0] != 'cat':
            return False
        if userargs[1] != self.file_path:
            return False
        if len(userargs) != 2:
            return False
        return True
