# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012 OpenStack Foundation.
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

import os
import StringIO
import urllib

import mock
import urllib2
from oslo.config import cfg

from openstack.common import jsonutils
from openstack.common import policy
from tests import utils

CONF = cfg.CONF

TEST_VAR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                            '..', 'var'))

ENFORCER = policy.Enforcer()


class TestException(Exception):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class RulesTestCase(utils.BaseTestCase):

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

    def test_str(self):
        exemplar = """{
    "admin_or_owner": "role:admin or project_id:%(project_id)s"
}"""
        rules = policy.Rules(dict(
            admin_or_owner="role:admin or project_id:%(project_id)s",
        ))

        self.assertEqual(str(rules), exemplar)

    def test_str_true(self):
        exemplar = """{
    "admin_or_owner": ""
}"""
        rules = policy.Rules(dict(
            admin_or_owner=policy.TrueCheck(),
        ))

        self.assertEqual(str(rules), exemplar)


class PolicyBaseTestCase(utils.BaseTestCase):

    def setUp(self):
        super(PolicyBaseTestCase, self).setUp()
        CONF(args=['--config-dir', TEST_VAR_DIR])
        self.enforcer = ENFORCER

    def tearDown(self):
        super(PolicyBaseTestCase, self).tearDown()
        # Make sure the policy rules are reset for remaining tests
        self.enforcer.clear()


class EnforcerTest(PolicyBaseTestCase):

    def test_load_file(self):
        self.enforcer.load_rules(True)
        self.assertIsNotNone(self.enforcer.rules)
        self.assertIn('default', self.enforcer.rules)
        self.assertIn('admin', self.enforcer.rules)

    def test_reload(self):
        self.enforcer.set_rules({'test': 'test'})
        self.enforcer.load_rules(force_reload=True)

        self.assertNotEquals(self.enforcer.rules, {'test': 'test'})
        self.assertIn('default', self.enforcer.rules)

    def test_set_rules(self):
        # Make sure the rules are set properly
        self.enforcer.rules = None
        self.enforcer.set_rules({'test': 1})
        self.assertEqual(self.enforcer.rules, {'test': 1})

    def test_set_rules_type(self):
        self.assertRaises(TypeError,
                          self.enforcer.set_rules,
                          'dummy')

    def test_clear(self):
        # Make sure the rules are reset
        self.enforcer.rules = 'spam'
        self.enforcer.clear()
        self.assertEqual(self.enforcer.rules, {})


class FakeCheck(policy.BaseCheck):
    def __init__(self, result=None):
        self.result = result

    def __str__(self):
        return str(self.result)

    def __call__(self, target, creds, enforcer):
        if self.result is not None:
            return self.result
        return (target, creds, enforcer)


class CheckFunctionTestCase(PolicyBaseTestCase):

    def test_check_explicit(self):
        self.enforcer.load_rules()
        self.enforcer.rules = None
        rule = FakeCheck()
        result = self.enforcer.enforce(rule, "target", "creds")

        self.assertEqual(result, ("target", "creds", self.enforcer))
        self.assertEqual(self.enforcer.rules, None)

    def test_check_no_rules(self):
        self.enforcer.load_rules()
        self.enforcer.rules = None
        result = self.enforcer.enforce('rule', "target", "creds")

        self.assertEqual(result, False)
        self.assertEqual(self.enforcer.rules, None)

    def test_check_missing_rule(self):
        self.enforcer.rules = {}
        result = self.enforcer.enforce('rule', 'target', 'creds')

        self.assertEqual(result, False)

    def test_check_with_rule(self):
        self.enforcer.load_rules()
        self.enforcer.rules = dict(default=FakeCheck())
        result = self.enforcer.enforce("default", "target", "creds")

        self.assertEqual(result, ("target", "creds", self.enforcer))

    def test_check_raises(self):
        self.enforcer.rules = None

        try:
            self.enforcer.enforce('rule', 'target', 'creds',
                                  True, TestException, "arg1",
                                  "arg2", kw1="kwarg1", kw2="kwarg2")
        except TestException as exc:
            self.assertEqual(exc.args, ("arg1", "arg2"))
            self.assertEqual(exc.kwargs, dict(kw1="kwarg1", kw2="kwarg2"))
        else:
            self.fail("enforcer.enforce() failed to raise requested exception")


class FalseCheckTestCase(utils.BaseTestCase):
    def test_str(self):
        check = policy.FalseCheck()

        self.assertEqual(str(check), '!')

    def test_call(self):
        check = policy.FalseCheck()

        self.assertEqual(check('target', 'creds'), False)


class TrueCheckTestCase(utils.BaseTestCase):
    def test_str(self):
        check = policy.TrueCheck()

        self.assertEqual(str(check), '@')

    def test_call(self):
        check = policy.TrueCheck()

        self.assertEqual(check('target', 'creds'), True)


class CheckForTest(policy.Check):
    def __call__(self, target, creds, enforcer):
        pass


class CheckTestCase(utils.BaseTestCase):
    def test_init(self):
        check = CheckForTest('kind', 'match')

        self.assertEqual(check.kind, 'kind')
        self.assertEqual(check.match, 'match')

    def test_str(self):
        check = CheckForTest('kind', 'match')

        self.assertEqual(str(check), 'kind:match')


class NotCheckTestCase(utils.BaseTestCase):
    def test_init(self):
        check = policy.NotCheck('rule')

        self.assertEqual(check.rule, 'rule')

    def test_str(self):
        check = policy.NotCheck('rule')

        self.assertEqual(str(check), 'not rule')

    def test_call_true(self):
        rule = mock.Mock(return_value=True)
        check = policy.NotCheck(rule)

        self.assertEqual(check('target', 'cred'), False)
        rule.assert_called_once_with('target', 'cred')

    def test_call_false(self):
        rule = mock.Mock(return_value=False)
        check = policy.NotCheck(rule)

        self.assertEqual(check('target', 'cred'), True)
        rule.assert_called_once_with('target', 'cred')


class OrCheckTestCase(utils.BaseTestCase):
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


class ParseCheckTestCase(utils.BaseTestCase):
    def test_false(self):
        result = policy._parse_check('!')

        self.assertTrue(isinstance(result, policy.FalseCheck))

    def test_true(self):
        result = policy._parse_check('@')

        self.assertTrue(isinstance(result, policy.TrueCheck))

    def test_bad_rule(self):
        result = policy._parse_check('foobar')

        self.assertTrue(isinstance(result, policy.FalseCheck))

    @mock.patch.object(policy, '_checks', {})
    def test_no_handler(self):
        result = policy._parse_check('no:handler')

        self.assertTrue(isinstance(result, policy.FalseCheck))

    @mock.patch.object(policy, '_checks', {
        'spam': mock.Mock(return_value="spam_check"),
        None: mock.Mock(return_value="none_check"),
    })
    def test_check(self):
        result = policy._parse_check('spam:handler')

        self.assertEqual(result, 'spam_check')
        policy._checks['spam'].assert_called_once_with('spam', 'handler')
        self.assertFalse(policy._checks[None].called)

    @mock.patch.object(policy, '_checks', {
        None: mock.Mock(return_value="none_check"),
    })
    def test_check_default(self):
        result = policy._parse_check('spam:handler')

        self.assertEqual(result, 'none_check')
        policy._checks[None].assert_called_once_with('spam', 'handler')


class ParseListRuleTestCase(utils.BaseTestCase):
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


class ParseTokenizeTestCase(utils.BaseTestCase):
    @mock.patch.object(policy, '_parse_check', lambda x: x)
    def test_tokenize(self):
        exemplar = ("(( ( ((() And)) or ) (check:%(miss)s) not)) "
                    "'a-string' \"another-string\"")
        expected = [
            ('(', '('), ('(', '('), ('(', '('), ('(', '('), ('(', '('),
            ('(', '('), (')', ')'), ('and', 'And'),
            (')', ')'), (')', ')'), ('or', 'or'), (')', ')'), ('(', '('),
            ('check', 'check:%(miss)s'), (')', ')'), ('not', 'not'),
            (')', ')'), (')', ')'),
            ('string', 'a-string'),
            ('string', 'another-string'),
        ]

        result = list(policy._parse_tokenize(exemplar))

        self.assertEqual(result, expected)


class ParseStateMetaTestCase(utils.BaseTestCase):
    def test_reducer(self):
        @policy.reducer('a', 'b', 'c')
        @policy.reducer('d', 'e', 'f')
        def spam():
            pass

        self.assertTrue(hasattr(spam, 'reducers'))
        self.assertEqual(spam.reducers, [['d', 'e', 'f'], ['a', 'b', 'c']])

    def test_parse_state_meta(self):
        class FakeState(object):
            __metaclass__ = policy.ParseStateMeta

            @policy.reducer('a', 'b', 'c')
            @policy.reducer('d', 'e', 'f')
            def reduce1(self):
                pass

            @policy.reducer('g', 'h', 'i')
            def reduce2(self):
                pass

        self.assertTrue(hasattr(FakeState, 'reducers'))
        for reduction, reducer in FakeState.reducers:
            if (reduction == ['a', 'b', 'c'] or
                    reduction == ['d', 'e', 'f']):
                self.assertEqual(reducer, 'reduce1')
            elif reduction == ['g', 'h', 'i']:
                self.assertEqual(reducer, 'reduce2')
            else:
                self.fail("Unrecognized reducer discovered")


class ParseStateTestCase(utils.BaseTestCase):
    def test_init(self):
        state = policy.ParseState()

        self.assertEqual(state.tokens, [])
        self.assertEqual(state.values, [])

    @mock.patch.object(policy.ParseState, 'reducers', [(['tok1'], 'meth')])
    @mock.patch.object(policy.ParseState, 'meth', create=True)
    def test_reduce_none(self, mock_meth):
        state = policy.ParseState()
        state.tokens = ['tok2']
        state.values = ['val2']

        state.reduce()

        self.assertEqual(state.tokens, ['tok2'])
        self.assertEqual(state.values, ['val2'])
        self.assertFalse(mock_meth.called)

    @mock.patch.object(policy.ParseState, 'reducers',
                       [(['tok1', 'tok2'], 'meth')])
    @mock.patch.object(policy.ParseState, 'meth', create=True)
    def test_reduce_short(self, mock_meth):
        state = policy.ParseState()
        state.tokens = ['tok1']
        state.values = ['val1']

        state.reduce()

        self.assertEqual(state.tokens, ['tok1'])
        self.assertEqual(state.values, ['val1'])
        self.assertFalse(mock_meth.called)

    @mock.patch.object(policy.ParseState, 'reducers',
                       [(['tok1', 'tok2'], 'meth')])
    @mock.patch.object(policy.ParseState, 'meth', create=True,
                       return_value=[('tok3', 'val3')])
    def test_reduce_one(self, mock_meth):
        state = policy.ParseState()
        state.tokens = ['tok1', 'tok2']
        state.values = ['val1', 'val2']

        state.reduce()

        self.assertEqual(state.tokens, ['tok3'])
        self.assertEqual(state.values, ['val3'])
        mock_meth.assert_called_once_with('val1', 'val2')

    @mock.patch.object(policy.ParseState, 'reducers', [
        (['tok1', 'tok4'], 'meth2'),
        (['tok2', 'tok3'], 'meth1'),
    ])
    @mock.patch.object(policy.ParseState, 'meth1', create=True,
                       return_value=[('tok4', 'val4')])
    @mock.patch.object(policy.ParseState, 'meth2', create=True,
                       return_value=[('tok5', 'val5')])
    def test_reduce_two(self, mock_meth2, mock_meth1):
        state = policy.ParseState()
        state.tokens = ['tok1', 'tok2', 'tok3']
        state.values = ['val1', 'val2', 'val3']

        state.reduce()

        self.assertEqual(state.tokens, ['tok5'])
        self.assertEqual(state.values, ['val5'])
        mock_meth1.assert_called_once_with('val2', 'val3')
        mock_meth2.assert_called_once_with('val1', 'val4')

    @mock.patch.object(policy.ParseState, 'reducers',
                       [(['tok1', 'tok2'], 'meth')])
    @mock.patch.object(policy.ParseState, 'meth', create=True,
                       return_value=[('tok3', 'val3'), ('tok4', 'val4')])
    def test_reduce_multi(self, mock_meth):
        state = policy.ParseState()
        state.tokens = ['tok1', 'tok2']
        state.values = ['val1', 'val2']

        state.reduce()

        self.assertEqual(state.tokens, ['tok3', 'tok4'])
        self.assertEqual(state.values, ['val3', 'val4'])
        mock_meth.assert_called_once_with('val1', 'val2')

    def test_shift(self):
        state = policy.ParseState()

        with mock.patch.object(policy.ParseState, 'reduce') as mock_reduce:
            state.shift('token', 'value')

            self.assertEqual(state.tokens, ['token'])
            self.assertEqual(state.values, ['value'])
            mock_reduce.assert_called_once_with()

    def test_result_empty(self):
        state = policy.ParseState()

        self.assertRaises(ValueError, lambda: state.result)

    def test_result_unreduced(self):
        state = policy.ParseState()
        state.tokens = ['tok1', 'tok2']
        state.values = ['val1', 'val2']

        self.assertRaises(ValueError, lambda: state.result)

    def test_result(self):
        state = policy.ParseState()
        state.tokens = ['token']
        state.values = ['value']

        self.assertEqual(state.result, 'value')

    def test_wrap_check(self):
        state = policy.ParseState()

        result = state._wrap_check('(', 'the_check', ')')

        self.assertEqual(result, [('check', 'the_check')])

    @mock.patch.object(policy, 'AndCheck', lambda x: x)
    def test_make_and_expr(self):
        state = policy.ParseState()

        result = state._make_and_expr('check1', 'and', 'check2')

        self.assertEqual(result, [('and_expr', ['check1', 'check2'])])

    def test_extend_and_expr(self):
        state = policy.ParseState()
        mock_expr = mock.Mock()
        mock_expr.add_check.return_value = 'newcheck'

        result = state._extend_and_expr(mock_expr, 'and', 'check')

        self.assertEqual(result, [('and_expr', 'newcheck')])
        mock_expr.add_check.assert_called_once_with('check')

    @mock.patch.object(policy, 'OrCheck', lambda x: x)
    def test_make_or_expr(self):
        state = policy.ParseState()

        result = state._make_or_expr('check1', 'or', 'check2')

        self.assertEqual(result, [('or_expr', ['check1', 'check2'])])

    def test_extend_or_expr(self):
        state = policy.ParseState()
        mock_expr = mock.Mock()
        mock_expr.add_check.return_value = 'newcheck'

        result = state._extend_or_expr(mock_expr, 'or', 'check')

        self.assertEqual(result, [('or_expr', 'newcheck')])
        mock_expr.add_check.assert_called_once_with('check')

    @mock.patch.object(policy, 'NotCheck', lambda x: 'not %s' % x)
    def test_make_not_expr(self):
        state = policy.ParseState()

        result = state._make_not_expr('not', 'check')

        self.assertEqual(result, [('check', 'not check')])


class ParseTextRuleTestCase(utils.BaseTestCase):
    def test_empty(self):
        result = policy._parse_text_rule('')

        self.assertTrue(isinstance(result, policy.TrueCheck))

    @mock.patch.object(policy, '_parse_tokenize',
                       return_value=[('tok1', 'val1'), ('tok2', 'val2')])
    @mock.patch.object(policy.ParseState, 'shift')
    @mock.patch.object(policy.ParseState, 'result', 'result')
    def test_shifts(self, mock_shift, mock_parse_tokenize):
        result = policy._parse_text_rule('test rule')

        self.assertEqual(result, 'result')
        mock_parse_tokenize.assert_called_once_with('test rule')
        mock_shift.assert_has_calls(
            [mock.call('tok1', 'val1'), mock.call('tok2', 'val2')])

    @mock.patch.object(policy, '_parse_tokenize', return_value=[])
    def test_fail(self, mock_parse_tokenize):
        result = policy._parse_text_rule('test rule')

        self.assertTrue(isinstance(result, policy.FalseCheck))
        mock_parse_tokenize.assert_called_once_with('test rule')


class ParseRuleTestCase(utils.BaseTestCase):
    @mock.patch.object(policy, '_parse_text_rule', return_value='text rule')
    @mock.patch.object(policy, '_parse_list_rule', return_value='list rule')
    def test_parse_rule_string(self, mock_parse_list_rule,
                               mock_parse_text_rule):
        result = policy.parse_rule("a string")

        self.assertEqual(result, 'text rule')
        self.assertFalse(mock_parse_list_rule.called)
        mock_parse_text_rule.assert_called_once_with('a string')

    @mock.patch.object(policy, '_parse_text_rule', return_value='text rule')
    @mock.patch.object(policy, '_parse_list_rule', return_value='list rule')
    def test_parse_rule_list(self, mock_parse_list_rule, mock_parse_text_rule):
        result = policy.parse_rule([['a'], ['list']])

        self.assertEqual(result, 'list rule')
        self.assertFalse(mock_parse_text_rule.called)
        mock_parse_list_rule.assert_called_once_with([['a'], ['list']])


class CheckRegisterTestCase(utils.BaseTestCase):
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


class RuleCheckTestCase(utils.BaseTestCase):
    @mock.patch.object(ENFORCER, 'rules', {})
    def test_rule_missing(self):
        check = policy.RuleCheck('rule', 'spam')

        self.assertEqual(check('target', 'creds', ENFORCER), False)

    @mock.patch.object(ENFORCER, 'rules',
                       dict(spam=mock.Mock(return_value=False)))
    def test_rule_false(self):
        enforcer = ENFORCER

        check = policy.RuleCheck('rule', 'spam')

        self.assertEqual(check('target', 'creds', enforcer), False)
        enforcer.rules['spam'].assert_called_once_with('target', 'creds',
                                                       enforcer)

    @mock.patch.object(ENFORCER, 'rules',
                       dict(spam=mock.Mock(return_value=True)))
    def test_rule_true(self):
        enforcer = ENFORCER
        check = policy.RuleCheck('rule', 'spam')

        self.assertEqual(check('target', 'creds', enforcer), True)
        enforcer.rules['spam'].assert_called_once_with('target', 'creds',
                                                       enforcer)


class RoleCheckTestCase(PolicyBaseTestCase):
    def test_accept(self):
        check = policy.RoleCheck('role', 'sPaM')

        self.assertEqual(check('target', dict(roles=['SpAm']),
                               self.enforcer), True)

    def test_reject(self):
        check = policy.RoleCheck('role', 'spam')

        self.assertEqual(check('target', dict(roles=[]), self.enforcer), False)


class HttpCheckTestCase(PolicyBaseTestCase):
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
                               dict(user='user', roles=['a', 'b', 'c']),
                               self.enforcer),
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
                               dict(user='user', roles=['a', 'b', 'c']),
                               self.enforcer),
                         False)
        self.assertEqual(mock_urlopen.call_count, 1)

        args = mock_urlopen.call_args[0]

        self.assertEqual(args[0], 'http://example.com/target')
        self.assertEqual(self.decode_post_data(args[1]), dict(
            target=dict(name='target', spam='spammer'),
            credentials=dict(user='user', roles=['a', 'b', 'c']),
        ))


class GenericCheckTestCase(PolicyBaseTestCase):
    def test_no_cred(self):
        check = policy.GenericCheck('name', '%(name)s')

        self.assertEqual(check(dict(name='spam'), {}, self.enforcer), False)

    def test_cred_mismatch(self):
        check = policy.GenericCheck('name', '%(name)s')

        self.assertEqual(check(dict(name='spam'),
                               dict(name='ham'),
                               self.enforcer), False)

    def test_accept(self):
        check = policy.GenericCheck('name', '%(name)s')

        self.assertEqual(check(dict(name='spam'),
                               dict(name='spam'),
                               self.enforcer), True)
