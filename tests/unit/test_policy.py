# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012 OpenStack, LLC.
# All Rights Reserved.

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

"""Test of Policy Engine"""

import os.path
import StringIO
import unittest
import urllib

import mock
import urllib2

from openstack.common import jsonutils
from openstack.common import policy


class TestException(Exception):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class RulesTestCase(unittest.TestCase):
    def test_init_basic(self):
        rules = policy.Rules()

        self.assertEqual(rules, {})
        self.assertEqual(rules.default_rule, None)

    def test_init(self):
        rules = policy.Rules(dict(a=1, b=2, c=3), 'a')

        self.assertEqual(rules, dict(a=1, b=2, c=3))
        self.assertEqual(rules.default_rule, 'a')

    def test_no_default(self):
        rules = policy.Rules(dict(a=1, b=2, c=3))

        self.assertRaises(KeyError, lambda: rules['d'])

    def test_missing_default(self):
        rules = policy.Rules(dict(a=1, c=3), 'b')

        self.assertRaises(KeyError, lambda: rules['d'])

    def test_with_default(self):
        rules = policy.Rules(dict(a=1, b=2, c=3), 'b')

        self.assertEqual(rules['d'], 2)

    def test_retrieval(self):
        rules = policy.Rules(dict(a=1, b=2, c=3), 'b')

        self.assertEqual(rules['a'], 1)
        self.assertEqual(rules['b'], 2)
        self.assertEqual(rules['c'], 3)

    @mock.patch.object(policy, 'parse_rule', lambda x: x)
    def test_load_json(self):
        exemplar = """{
    "admin_or_owner": [["role:admin"], ["project_id:%(project_id)s"]],
    "default": []
}"""
        rules = policy.Rules.load_json(exemplar, 'default')

        self.assertEqual(rules.default_rule, 'default')
        self.assertEqual(rules, dict(
            admin_or_owner=[["role:admin"], ["project_id:%(project_id)s"]],
            default=[],
        ))

    def test_str_true(self):
        exemplar = """{
    "admin_or_owner": ""
}"""
        rules = policy.Rules(dict(
            admin_or_owner=policy.TrueCheck(),
        ))

        self.assertEqual(str(rules), exemplar)


class PolicySetAndResetTestCase(unittest.TestCase):
    def tearDown(self):
        # Make sure the policy rules are reset for remaining tests
        policy._rules = None

    def test_set_rules(self):
        # Make sure the rules are set properly
        policy._rules = None
        policy.set_rules('spam')
        self.assertEqual(policy._rules, 'spam')

    def test_set_brain(self):
        # Make sure the brain is set properly
        policy._rules = None
        policy.set_brain('spam')
        self.assertEqual(policy._rules, 'spam')

    def test_reset(self):
        # Make sure the rules are reset
        policy._rules = 'spam'
        policy.reset()
        self.assertEqual(policy._rules, None)


class FakeCheck(policy.BaseCheck):
    def __init__(self, result=None):
        self.result = result

    def __str__(self):
        return self.result

    def __call__(self, target, creds):
        if self.result is not None:
            return self.result
        return (target, creds)


class CheckFunctionTestCase(unittest.TestCase):
    def tearDown(self):
        # Make sure the policy rules are reset for remaining tests
        policy._rules = None

    def test_check_explicit(self):
        policy._rules = None
        rule = FakeCheck()
        result = policy.check(rule, "target", "creds")

        self.assertEqual(result, ("target", "creds"))
        self.assertEqual(policy._rules, None)

    def test_check_no_rules(self):
        policy._rules = None
        result = policy.check('rule', "target", "creds")

        self.assertEqual(result, False)
        self.assertEqual(policy._rules, None)

    def test_check_missing_rule(self):
        policy._rules = {}
        result = policy.check('rule', 'target', 'creds')

        self.assertEqual(result, False)

    def test_check_with_rule(self):
        policy._rules = dict(default=FakeCheck())
        result = policy.check("default", "target", "creds")

        self.assertEqual(result, ("target", "creds"))

    def test_check_raises(self):
        policy._rules = None

        try:
            result = policy.check('rule', 'target', 'creds', TestException,
                                  "arg1", "arg2", kw1="kwarg1", kw2="kwarg2")
        except TestException as exc:
            self.assertEqual(exc.args, ("arg1", "arg2"))
            self.assertEqual(exc.kwargs, dict(kw1="kwarg1", kw2="kwarg2"))
        else:
            self.fail("policy.check() failed to raise requested exception")


class BrainTestCase(unittest.TestCase):
    def test_basic_init(self):
        brain = policy.Brain()

        self.assertEqual(brain, {})
        self.assertEqual(brain.rules, {})
        self.assertEqual(brain.default_rule, None)

    @mock.patch.object(policy, 'parse_rule', lambda x: x)
    def test_init_with_args(self):
        brain = policy.Brain(rules=dict(a="foo", b="bar"), default_rule="a")

        self.assertEqual(brain, dict(a="foo", b="bar"))
        self.assertEqual(brain.rules, dict(a="foo", b="bar"))
        self.assertEqual(brain.default_rule, "a")

    @mock.patch.object(policy, 'parse_rule', lambda x: x)
    def test_init_with_checks(self):
        exemplar = dict(a=FakeCheck("a"), b=FakeCheck("b"))
        brain = policy.Brain(rules=exemplar, default_rule="a")

        self.assertEqual(brain, exemplar)
        self.assertEqual(brain.rules, exemplar)
        self.assertEqual(brain.default_rule, "a")

    @mock.patch.object(policy, 'parse_rule', lambda x: x)
    def test_add_rule(self):
        brain = policy.Brain()
        brain.add_rule("rule1",
                       [["role:admin"], ["project_id:%(project_id)s"]])

        self.assertEqual(
            brain.rules, dict(
                rule1=[["role:admin"], ["project_id:%(project_id)s"]]))

    @mock.patch.object(policy, 'parse_rule', lambda x: x)
    def test_check(self):
        brain = policy.Brain()
        result = brain.check(FakeCheck(), 'target', 'creds')

        self.assertEqual(result, ('target', 'creds'))


class PolicyEnforceTestCase(unittest.TestCase):
    @mock.patch.object(policy, 'parse_rule', lambda x: 'spam')
    def test_enforce(self):
        with mock.patch.object(policy, 'check') as mock_check:
            mock_check.return_value = "result"

            result = policy.enforce("fake_check", 'target', 'creds',
                                    'exception', 'arg1', 'arg2',
                                    kw1='kwarg1', kw2='kwarg2')

            self.assertEqual(result, 'result')
            mock_check.assert_called_once_with('spam', 'target', 'creds',
                                               'exception', 'arg1', 'arg2',
                                               kw1='kwarg1', kw2='kwarg2')


class FalseCheckTestCase(unittest.TestCase):
    def test_str(self):
        check = policy.FalseCheck()

        self.assertEqual(str(check), '!')

    def test_call(self):
        check = policy.FalseCheck()

        self.assertEqual(check('target', 'creds'), False)


class TrueCheckTestCase(unittest.TestCase):
    def test_str(self):
        check = policy.TrueCheck()

        self.assertEqual(str(check), '@')

    def test_call(self):
        check = policy.TrueCheck()

        self.assertEqual(check('target', 'creds'), True)


class CheckForTest(policy.Check):
    def __call__(self, target, creds):
        pass


class CheckTestCase(unittest.TestCase):
    def test_init(self):
        check = CheckForTest('kind', 'match')

        self.assertEqual(check.kind, 'kind')
        self.assertEqual(check.match, 'match')

    def test_str(self):
        check = CheckForTest('kind', 'match')

        self.assertEqual(str(check), 'kind:match')


class FuncCheckTestCase(unittest.TestCase):
    def test_init(self):
        check = policy.FuncCheck('func', 'kind', 'match')

        self.assertEqual(check.func, 'func')
        self.assertEqual(check.kind, 'kind')
        self.assertEqual(check.match, 'match')

    def test_str(self):
        check = policy.FuncCheck('func', 'kind', 'match')

        self.assertEqual(str(check), 'kind:match')

    def test_call(self):
        check = policy.FuncCheck(lambda a, b, c, d, e: (a, b, c, d, e),
                                 'kind', 'match')

        self.assertEqual(check('target', 'creds'),
                         (None, 'kind', 'match', 'target', 'creds'))


class OrCheckTestCase(unittest.TestCase):
    def test_init(self):
        check = policy.OrCheck(['rule1', 'rule2'])

        self.assertEqual(check.rules, ['rule1', 'rule2'])

    def test_add_check(self):
        check = policy.OrCheck(['rule1', 'rule2'])
        check.add_check('rule3')

        self.assertEqual(check.rules, ['rule1', 'rule2', 'rule3'])

    def test_str(self):
        check = policy.OrCheck(['rule1', 'rule2'])

        self.assertEqual(str(check), '(rule1 or rule2)')

    def test_call_all_false(self):
        rules = [mock.Mock(return_value=False), mock.Mock(return_value=False)]
        check = policy.OrCheck(rules)

        self.assertEqual(check('target', 'cred'), False)
        rules[0].assert_called_once_with('target', 'cred')
        rules[1].assert_called_once_with('target', 'cred')

    def test_call_first_true(self):
        rules = [mock.Mock(return_value=True), mock.Mock(return_value=False)]
        check = policy.OrCheck(rules)

        self.assertEqual(check('target', 'cred'), True)
        rules[0].assert_called_once_with('target', 'cred')
        self.assertFalse(rules[1].called)

    def test_call_second_true(self):
        rules = [mock.Mock(return_value=False), mock.Mock(return_value=True)]
        check = policy.OrCheck(rules)

        self.assertEqual(check('target', 'cred'), True)
        rules[0].assert_called_once_with('target', 'cred')
        rules[1].assert_called_once_with('target', 'cred')


class ParseCheckTestCase(unittest.TestCase):
    def test_bad_rule(self):
        result = policy._parse_check('foobar')

        self.assertTrue(isinstance(result, policy.FalseCheck))

    @mock.patch.object(policy, '_checks', {})
    @mock.patch.object(policy, '_functions', {})
    def test_no_handler(self):
        result = policy._parse_check('no:handler')

        self.assertTrue(isinstance(result, policy.FalseCheck))

    @mock.patch.object(policy, '_checks', {
        'spam': mock.Mock(return_value="spam_check"),
        None: mock.Mock(return_value="none_check"),
    })
    @mock.patch.object(policy, '_functions', {
        'spam': "spam_func",
        None: "none_func",
    })
    def test_check(self):
        result = policy._parse_check('spam:handler')

        self.assertEqual(result, 'spam_check')
        policy._checks['spam'].assert_called_once_with('spam', 'handler')
        self.assertFalse(policy._checks[None].called)

    @mock.patch.object(policy, '_checks', {
        None: mock.Mock(return_value="none_check"),
    })
    @mock.patch.object(policy, '_functions', {
        'spam': "spam_func",
        None: "none_func",
    })
    def test_func(self):
        result = policy._parse_check('spam:handler')

        self.assertTrue(isinstance(result, policy.FuncCheck))
        self.assertEqual(result.func, 'spam_func')
        self.assertEqual(result.kind, 'spam')
        self.assertEqual(result.match, 'handler')
        self.assertFalse(policy._checks[None].called)

    @mock.patch.object(policy, '_checks', {
        None: mock.Mock(return_value="none_check"),
    })
    @mock.patch.object(policy, '_functions', {
        None: "none_func",
    })
    def test_check_default(self):
        result = policy._parse_check('spam:handler')

        self.assertEqual(result, 'none_check')
        policy._checks[None].assert_called_once_with('spam', 'handler')

    @mock.patch.object(policy, '_checks', {})
    @mock.patch.object(policy, '_functions', {
        None: "none_func",
    })
    def test_func_default(self):
        result = policy._parse_check('spam:handler')

        self.assertTrue(isinstance(result, policy.FuncCheck))
        self.assertEqual(result.func, 'none_func')
        self.assertEqual(result.kind, 'spam')
        self.assertEqual(result.match, 'handler')


class ParseListRuleTestCase(unittest.TestCase):
    def test_empty(self):
        result = policy._parse_list_rule([])

        self.assertTrue(isinstance(result, policy.TrueCheck))
        self.assertEqual(str(result), '@')

    @mock.patch.object(policy, '_parse_check', FakeCheck)
    def test_oneele_zeroele(self):
        result = policy._parse_list_rule([[]])

        self.assertTrue(isinstance(result, policy.FalseCheck))
        self.assertEqual(str(result), '!')

    @mock.patch.object(policy, '_parse_check', FakeCheck)
    def test_oneele_bare(self):
        result = policy._parse_list_rule(['rule'])

        self.assertTrue(isinstance(result, FakeCheck))
        self.assertEqual(result.result, 'rule')
        self.assertEqual(str(result), 'rule')

    @mock.patch.object(policy, '_parse_check', FakeCheck)
    def test_oneele_oneele(self):
        result = policy._parse_list_rule([['rule']])

        self.assertTrue(isinstance(result, FakeCheck))
        self.assertEqual(result.result, 'rule')
        self.assertEqual(str(result), 'rule')

    @mock.patch.object(policy, '_parse_check', FakeCheck)
    def test_oneele_multi(self):
        result = policy._parse_list_rule([['rule1', 'rule2']])

        self.assertTrue(isinstance(result, policy.AndCheck))
        self.assertEqual(len(result.rules), 2)
        for i, value in enumerate(['rule1', 'rule2']):
            self.assertTrue(isinstance(result.rules[i], FakeCheck))
            self.assertEqual(result.rules[i].result, value)
        self.assertEqual(str(result), '(rule1 and rule2)')

    @mock.patch.object(policy, '_parse_check', FakeCheck)
    def test_multi_oneele(self):
        result = policy._parse_list_rule([['rule1'], ['rule2']])

        self.assertTrue(isinstance(result, policy.OrCheck))
        self.assertEqual(len(result.rules), 2)
        for i, value in enumerate(['rule1', 'rule2']):
            self.assertTrue(isinstance(result.rules[i], FakeCheck))
            self.assertEqual(result.rules[i].result, value)
        self.assertEqual(str(result), '(rule1 or rule2)')

    @mock.patch.object(policy, '_parse_check', FakeCheck)
    def test_multi_multi(self):
        result = policy._parse_list_rule([['rule1', 'rule2'],
                                          ['rule3', 'rule4']])

        self.assertTrue(isinstance(result, policy.OrCheck))
        self.assertEqual(len(result.rules), 2)
        for i, values in enumerate([['rule1', 'rule2'], ['rule3', 'rule4']]):
            self.assertTrue(isinstance(result.rules[i], policy.AndCheck))
            self.assertEqual(len(result.rules[i].rules), 2)
            for j, value in enumerate(values):
                self.assertTrue(isinstance(result.rules[i].rules[j],
                                           FakeCheck))
                self.assertEqual(result.rules[i].rules[j].result, value)
        self.assertEqual(str(result),
                         '((rule1 and rule2) or (rule3 and rule4))')


class CheckRegisterTestCase(unittest.TestCase):
    @mock.patch.object(policy, '_functions', {})
    def test_register_func(self):
        def test_func():
            pass

        policy.register('spam', test_func)

        self.assertEqual(policy._functions, dict(spam=test_func))

    @mock.patch.object(policy, '_functions', {})
    def test_register_func_decorator(self):
        @policy.register('spam')
        def test_func():
            pass

        self.assertEqual(policy._functions, dict(spam=test_func))

    @mock.patch.object(policy, '_checks', {})
    def test_register_check(self):
        class TestCheck(policy.Check):
            pass

        policy.register('spam', TestCheck)

        self.assertEqual(policy._checks, dict(spam=TestCheck))

    @mock.patch.object(policy, '_checks', {})
    def test_register_check_decorator(self):
        @policy.register('spam')
        class TestCheck(policy.Check):
            pass

        self.assertEqual(policy._checks, dict(spam=TestCheck))


class RuleCheckTestCase(unittest.TestCase):
    @mock.patch.object(policy, '_rules', {})
    def test_rule_missing(self):
        check = policy.RuleCheck('rule', 'spam')

        self.assertEqual(check('target', 'creds'), False)

    @mock.patch.object(policy, '_rules',
                       dict(spam=mock.Mock(return_value=False)))
    def test_rule_false(self):
        check = policy.RuleCheck('rule', 'spam')

        self.assertEqual(check('target', 'creds'), False)
        policy._rules['spam'].assert_called_once_with('target', 'creds')

    @mock.patch.object(policy, '_rules',
                       dict(spam=mock.Mock(return_value=True)))
    def test_rule_true(self):
        check = policy.RuleCheck('rule', 'spam')

        self.assertEqual(check('target', 'creds'), True)
        policy._rules['spam'].assert_called_once_with('target', 'creds')


class RoleCheckTestCase(unittest.TestCase):
    def test_accept(self):
        check = policy.RoleCheck('role', 'sPaM')

        self.assertEqual(check('target', dict(roles=['SpAm'])), True)

    def test_reject(self):
        check = policy.RoleCheck('role', 'spam')

        self.assertEqual(check('target', dict(roles=[])), False)


class HttpCheckTestCase(unittest.TestCase):
    def decode_post_data(self, post_data):
        result = {}
        for item in post_data.split('&'):
            key, _sep, value = item.partition('=')
            result[key] = jsonutils.loads(urllib.unquote_plus(value))

        return result

    @mock.patch.object(urllib2, 'urlopen',
                       return_value=StringIO.StringIO('True'))
    def test_accept(self, mock_urlopen):
        check = policy.HttpCheck('http', '//example.com/%(name)s')

        self.assertEqual(check(dict(name='target', spam='spammer'),
                               dict(user='user', roles=['a', 'b', 'c'])),
                         True)
        self.assertEqual(mock_urlopen.call_count, 1)

        args = mock_urlopen.call_args[0]

        self.assertEqual(args[0], 'http://example.com/target')
        self.assertEqual(self.decode_post_data(args[1]), dict(
            target=dict(name='target', spam='spammer'),
            credentials=dict(user='user', roles=['a', 'b', 'c']),
        ))

    @mock.patch.object(urllib2, 'urlopen',
                       return_value=StringIO.StringIO('other'))
    def test_reject(self, mock_urlopen):
        check = policy.HttpCheck('http', '//example.com/%(name)s')

        self.assertEqual(check(dict(name='target', spam='spammer'),
                               dict(user='user', roles=['a', 'b', 'c'])),
                         False)
        self.assertEqual(mock_urlopen.call_count, 1)

        args = mock_urlopen.call_args[0]

        self.assertEqual(args[0], 'http://example.com/target')
        self.assertEqual(self.decode_post_data(args[1]), dict(
            target=dict(name='target', spam='spammer'),
            credentials=dict(user='user', roles=['a', 'b', 'c']),
        ))


class GenericCheckTestCase(unittest.TestCase):
    def test_no_cred(self):
        check = policy.GenericCheck('name', '%(name)s')

        self.assertEqual(check(dict(name='spam'), {}), False)

    def test_cred_mismatch(self):
        check = policy.GenericCheck('name', '%(name)s')

        self.assertEqual(check(dict(name='spam'), dict(name='ham')), False)

    def test_accept(self):
        check = policy.GenericCheck('name', '%(name)s')

        self.assertEqual(check(dict(name='spam'), dict(name='spam')), True)
