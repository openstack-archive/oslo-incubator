# Copyright (c) 2012 OpenStack Foundation.
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
Common Policy Enforcer Implementation

The policy enforcer handles the way policies are checked.
It also reads and loads rules dynamically, so that services does not
have to be restarted when the policy file is updated.
"""

from oslo.config import cfg

from openstack.common import fileutils
from openstack.common.gettextutils import _, _LE
from openstack.common import jsonutils
from openstack.common import log as logging
from openstack.common import policy_parser as parser

policy_opts = [
    cfg.StrOpt('policy_file',
               default='policy.json',
               help=_('The JSON file that defines policies.')),
    cfg.StrOpt('policy_default_rule',
               default='default',
               help=_('Default rule. Enforced when a requested rule is not '
                      'found.')),
]

CONF = cfg.CONF
CONF.register_opts(policy_opts)

LOG = logging.getLogger(__name__)

# adapt parser to work with our enforcer.
parser.registry.register('rule_formatter', jsonutils)
parser.registry.register('trans', _)
parser.registry.register('trans_error', _LE)
parser.registry.register('logger', LOG)


class Enforcer(object):
    """Responsible for loading and enforcing rules.

    :param policy_file: Custom policy file to use, if none is
                        specified, `CONF.policy_file` will be
                        used.
    :param rules: Default dictionary / Rules to use. It will be
                  considered just in the first instantiation. If
                  `load_rules(True)`, `clear()` or `set_rules(True)`
                  is called this will be overwritten.
    :param default_rule: Default rule to use, CONF.default_rule will
                         be used if none is specified.
    :param use_conf: Whether to load rules from cache or config file.
    """

    def __init__(self, policy_file=None, rules=None,
                 default_rule=None, use_conf=True):
        self.rules = parser.Rules(rules, default_rule)
        self.default_rule = default_rule or CONF.policy_default_rule

        self.policy_path = None
        self.policy_file = policy_file or CONF.policy_file
        self.use_conf = use_conf

    def set_rules(self, rules, overwrite=True, use_conf=False):
        """Create a new Rules object based on the provided dict of rules.

        :param rules: New rules to use. It should be an instance of dict.
        :param overwrite: Whether to overwrite current rules or update them
                          with the new rules.
        :param use_conf: Whether to reload rules from cache or config file.
        """

        if not isinstance(rules, dict):
            raise TypeError(_("Rules must be an instance of dict or Rules, "
                            "got %s instead") % type(rules))
        self.use_conf = use_conf
        if overwrite:
            self.rules = parser.Rules(rules, self.default_rule)
        else:
            self.rules.update(rules)

    def clear(self):
        """Clears Enforcer rules, policy's cache and policy's path."""
        self.set_rules({})
        self.default_rule = None
        self.policy_path = None

    def load_rules(self, force_reload=False):
        """Loads policy_path's rules.

        Policy file is cached and will be reloaded if modified.

        :param force_reload: Whether to overwrite current rules.
        """

        if force_reload:
            self.use_conf = force_reload

        if self.use_conf:
            if not self.policy_path:
                self.policy_path = self._get_policy_path()

            reloaded, data = fileutils.read_cached_file(
                self.policy_path, force_reload=force_reload)
            if reloaded or not self.rules:
                rules = parser.Rules.load_json(data, self.default_rule)
                self.set_rules(rules)
                LOG.debug("Rules successfully reloaded")

    def _get_policy_path(self):
        """Locate the policy json data file.

        :param policy_file: Custom policy file to locate.

        :returns: The policy path

        :raises: ConfigFilesNotFoundError if the file couldn't
                 be located.
        """
        policy_file = CONF.find_file(self.policy_file)

        if policy_file:
            return policy_file

        raise cfg.ConfigFilesNotFoundError((self.policy_file,))

    def enforce(self, rule, target, creds, do_raise=False,
                exc=None, *args, **kwargs):
        """Checks authorization of a rule against the target and credentials.

        :param rule: A string or BaseCheck instance specifying the rule
                    to evaluate.
        :param target: As much information about the object being operated
                    on as possible, as a dictionary.
        :param creds: As much information about the user performing the
                    action as possible, as a dictionary.
        :param do_raise: Whether to raise an exception or not if check
                        fails.
        :param exc: Class of the exception to raise if the check fails.
                    Any remaining arguments passed to check() (both
                    positional and keyword arguments) will be passed to
                    the exception class. If not specified, PolicyNotAuthorized
                    will be used.

        :return: Returns False if the policy does not allow the action and
                exc is not provided; otherwise, returns a value that
                evaluates to True.  Note: for rules using the "case"
                expression, this True value will be the specified string
                from the expression.
        """

        # NOTE(flaper87): Not logging target or creds to avoid
        # potential security issues.
        LOG.debug("Rule %s will be now enforced" % rule)

        self.load_rules()

        # Allow the rule to be a Check tree
        if isinstance(rule, parser.BaseCheck):
            result = rule(target, creds, self)
        elif not self.rules:
            # No rules to reference means we're going to fail closed
            result = False
        else:
            try:
                # Evaluate the rule
                result = self.rules[rule](target, creds, self)
            except KeyError:
                LOG.debug("Rule [%s] doesn't exist" % rule)
                # If the rule doesn't exist, fail closed
                result = False

        # If it is False, raise the exception if requested
        if do_raise and not result:
            if exc:
                raise exc(*args, **kwargs)

            raise parser.PolicyNotAuthorized(rule)

        return result
