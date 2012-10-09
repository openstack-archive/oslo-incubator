# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012 OpenStack, LLC.
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
Common Policy Engine Implementation

Policies are be expressed as a list-of-lists where each check inside the
innermost list is combined as with an "and" conjunction--for that check to
pass, all the specified checks must pass.  These innermost lists are then
combined as with an "or" conjunction.

As an example, take the following rule, expressed in the list-of-lists
representation::

    [["role:admin"], ["project_id:%(project_id)s", "role:projectadmin"]]
"""

import abc
import logging
import urllib

import urllib2

from openstack.common.gettextutils import _
from openstack.common import jsonutils


LOG = logging.getLogger(__name__)


_rules = None
_checks = {}


class Rules(dict):
    """
    A store for rules.  Handles the default_rule setting directly.
    """

    @classmethod
    def load_json(cls, data, default_rule=None):
        """
        Allow loading of JSON rule data.
        """

        # Suck in the JSON data and parse the rules
        rules = dict((k, parse_rule(v)) for k, v in
                     jsonutils.loads(data).items())

        return cls(rules, default_rule)

    def __init__(self, rules=None, default_rule=None):
        """Initialize the Rules store."""

        super(Rules, self).__init__(rules or {})
        self.default_rule = default_rule

    def __missing__(self, key):
        """Implements the default rule handling."""

        # If the default rule isn't actually defined, do something
        # reasonably intelligent
        if not self.default_rule or self.default_rule not in self:
            raise KeyError(key)

        return self[self.default_rule]

    def __str__(self):
        """Dumps a string representation of the rules."""

        # Start by building the canonical strings for the rules
        out_rules = {}
        for key, value in self.items():
            # Use empty string for singleton TrueCheck instances
            if isinstance(value, TrueCheck):
                out_rules[key] = ''
            else:
                out_rules[key] = str(value)

        # Dump a pretty-printed JSON representation
        return jsonutils.dumps(out_rules, indent=4)


# Really have to figure out a way to deprecate this
def set_rules(rules):
    """Set the rules in use for policy checks."""

    global _rules

    _rules = rules


# Ditto
def reset():
    """Clear the rules used for policy checks."""

    global _rules

    _rules = None


def check(rule, target, creds, exc=None, *args, **kwargs):
    """
    Checks authorization of a rule against the target and credentials.

    :param rule: The rule to evaluate.
    :param target: As much information about the object being operated
                   on as possible, as a dictionary.
    :param creds: As much information about the user performing the
                  action as possible, as a dictionary.
    :param exc: Class of the exception to raise if the check fails.
                Any remaining arguments passed to check() (both
                positional and keyword arguments) will be passed to
                the exception class.  If exc is not provided, returns
                False.

    :return: Returns False if the policy does not allow the action and
             exc is not provided; otherwise, returns a value that
             evaluates to True.  Note: for rules using the "case"
             expression, this True value will be the specified string
             from the expression.
    """

    # Allow the rule to be a Check tree
    if isinstance(rule, BaseCheck):
        result = rule(target, creds)
    elif not _rules:
        # No rules to reference means we're going to fail closed
        result = False
    else:
        try:
            # Evaluate the rule
            result = _rules[rule](target, creds)
        except KeyError:
            # If the rule doesn't exist, fail closed
            result = False

    # If it is False, raise the exception if requested
    if exc and result is False:
        raise exc(*args, **kwargs)

    return result


class BaseCheck(object):
    """
    Abstract base class for Check classes.
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __str__(self):
        """
        Retrieve a string representation of the Check tree rooted at
        this node.
        """

        pass

    @abc.abstractmethod
    def __call__(self, target, cred):
        """
        Perform the check.  Returns False to reject the access or a
        true value (not necessary True) to accept the access.
        """

        pass


class FalseCheck(BaseCheck):
    """
    A policy check that always returns False (disallow).
    """

    def __str__(self):
        """Return a string representation of this check."""

        return "!"

    def __call__(self, target, cred):
        """Check the policy."""

        return False


class TrueCheck(BaseCheck):
    """
    A policy check that always returns True (allow).
    """

    def __str__(self):
        """Return a string representation of this check."""

        return "@"

    def __call__(self, target, cred):
        """Check the policy."""

        return True


class Check(BaseCheck):
    """
    A base class to allow for user-defined policy checks.
    """

    def __init__(self, kind, match):
        """
        :param kind: The kind of the check, i.e., the field before the
                     ':'.
        :param match: The match of the check, i.e., the field after
                      the ':'.
        """

        self.kind = kind
        self.match = match

    def __str__(self):
        """Return a string representation of this check."""

        return "%s:%s" % (self.kind, self.match)


class AndCheck(BaseCheck):
    """
    A policy check that requires that a list of other checks all
    return True.  Implements the "and" operator.
    """

    def __init__(self, rules):
        """
        Initialize the 'and' check.

        :param rules: A list of rules that will be tested.
        """

        self.rules = rules

    def __str__(self):
        """Return a string representation of this check."""

        return "(%s)" % ' and '.join(str(r) for r in self.rules)

    def __call__(self, target, cred):
        """
        Check the policy.  Requires that all rules accept in order to
        return True.
        """

        for rule in self.rules:
            if not rule(target, cred):
                return False

        return True

    def add_check(self, rule):
        """
        Allows addition of another rule to the list of rules that will
        be tested.  Returns the AndCheck object for convenience.
        """

        self.rules.append(rule)
        return self


class OrCheck(BaseCheck):
    """
    A policy check that requires that at least one of a list of other
    checks returns True.  Implements the "or" operator.
    """

    def __init__(self, rules):
        """
        Initialize the 'or' check.

        :param rules: A list of rules that will be tested.
        """

        self.rules = rules

    def __str__(self):
        """Return a string representation of this check."""

        return "(%s)" % ' or '.join(str(r) for r in self.rules)

    def __call__(self, target, cred):
        """
        Check the policy.  Requires that at least one rule accept in
        order to return True.
        """

        for rule in self.rules:
            if rule(target, cred):
                return True

        return False

    def add_check(self, rule):
        """
        Allows addition of another rule to the list of rules that will
        be tested.  Returns the OrCheck object for convenience.
        """

        self.rules.append(rule)
        return self


def _parse_check(rule):
    """
    Parse a single base check rule into an appropriate Check object.
    """
    try:
        kind, match = rule.split(':', 1)
    except Exception:
        LOG.exception(_("Failed to understand rule %(rule)s") % locals())
        # If the rule is invalid, we'll fail closed
        return FalseCheck()

    # Find what implements the check
    if kind in _checks:
        return _checks[kind](kind, match)
    elif None in _checks:
        return _checks[None](kind, match)
    else:
        LOG.error(_("No handler for matches of kind %s") % kind)
        return FalseCheck()


def _parse_list_rule(rule):
    """
    Provided for backwards compatibility.  Translates the old
    list-of-lists syntax into a tree of Check objects.
    """

    # Empty rule defaults to True
    if not rule:
        return TrueCheck()

    # Outer list is joined by "or"; inner list by "and"
    or_list = []
    for inner_rule in rule:
        # Elide empty inner lists
        if not inner_rule:
            continue

        # Handle bare strings
        if isinstance(inner_rule, basestring):
            inner_rule = [inner_rule]

        # Parse the inner rules into Check objects
        and_list = [_parse_check(r) for r in inner_rule]

        # Append the appropriate check to the or_list
        if len(and_list) == 1:
            or_list.append(and_list[0])
        else:
            or_list.append(AndCheck(and_list))

    # If we have only one check, omit the "or"
    if len(or_list) == 0:
        return FalseCheck()
    elif len(or_list) == 1:
        return or_list[0]

    return OrCheck(or_list)


def parse_rule(rule):
    """
    Parses a policy rule into a tree of Check objects.
    """
    return _parse_list_rule(rule)


def register(name, func=None):
    """
    Register a function or Check class as a policy check.

    :param name: Gives the name of the check type, e.g., 'rule',
                 'role', etc.  If name is None, a default check type
                 will be registered.
    :param func: If given, provides the function or class to register.
                 If not given, returns a function taking one argument
                 to specify the function or class to register,
                 allowing use as a decorator.
    """

    # Perform the actual decoration by registering the function or
    # class.  Returns the function or class for compliance with the
    # decorator interface.
    def decorator(func):
        global _checks
        _checks[name] = func
        return func

    # If the function or class is given, do the registration
    if func:
        return decorator(func)

    return decorator


@register("rule")
class RuleCheck(Check):
    def __call__(self, target, creds):
        """
        Recursively checks credentials based on the defined rules.
        """

        try:
            return _rules[self.match](target, creds)
        except KeyError:
            # We don't have any matching rule; fail closed
            return False


@register("role")
class RoleCheck(Check):
    def __call__(self, target, creds):
        """Check that there is a matching role in the cred dict."""

        return self.match.lower() in [x.lower() for x in creds['roles']]


@register('http')
class HttpCheck(Check):
    def __call__(self, target, creds):
        """
        Check http: rules by calling to a remote server.

        This example implementation simply verifies that the response
        is exactly 'True'.
        """

        url = ('http:' + self.match) % target
        data = {'target': jsonutils.dumps(target),
                'credentials': jsonutils.dumps(creds)}
        post_data = urllib.urlencode(data)
        f = urllib2.urlopen(url, post_data)
        return f.read() == "True"


@register(None)
class GenericCheck(Check):
    def __call__(self, target, creds):
        """
        Check an individual match.

        Matches look like:

            tenant:%(tenant_id)s
            role:compute:admin
        """

        # TODO(termie): do dict inspection via dot syntax
        match = self.match % target
        if self.kind in creds:
            return match == unicode(creds[self.kind])
        return False
