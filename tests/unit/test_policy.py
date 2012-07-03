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

"""Test of Policy Engine For Nova"""

import os.path
import StringIO
import unittest
import urllib

import mock
import urllib2

from openstack.common import jsonutils
from openstack.common import policy


class PolicySetAndResetTestCase(unittest.TestCase):
    def tearDown(self):
        # Make sure the policy brain is reset for remaining tests
        policy._BRAIN = None

    def test_set_brain(self):
        # Make sure the brain is set properly
        policy._BRAIN = None
        policy.set_brain('spam')
        self.assertEqual(policy._BRAIN, 'spam')

    def test_reset(self):
        # Make sure the brain is set to something
        policy._BRAIN = 'spam'
        policy.reset()
        self.assertEqual(policy._BRAIN, None)


class FakeBrain(object):
    check_result = True

    def check(self, match_list, target_dict, credentials_dict):
        self.match_list = match_list
        self.target_dict = target_dict
        self.credentials_dict = credentials_dict
        return self.check_result


class PolicyEnforceTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_brain = FakeBrain()
        policy._BRAIN = self.fake_brain

    def tearDown(self):
        policy.reset()

    def check_args(self, match_list, target_dict, credentials_dict):
        self.assertEqual(self.fake_brain.match_list, match_list)
        self.assertEqual(self.fake_brain.target_dict, target_dict)
        self.assertEqual(self.fake_brain.credentials_dict, credentials_dict)

    def test_make_new_brain(self):
        with mock.patch.object(policy, "Brain") as fake_brain:
            fake_brain.check.return_value = True

            result = policy.enforce("match", "target", "credentials")

            self.assertNotEqual(policy._BRAIN, None)
            self.assertEqual(result, True)

    def test_use_existing_brain(self):
        result = policy.enforce("match", "target", "credentials")

        self.assertNotEqual(policy._BRAIN, None)
        self.assertEqual(result, True)
        self.check_args("match", "target", "credentials")

    def test_fail_no_exc(self):
        self.fake_brain.check_result = False
        result = policy.enforce("match", "target", "credentials")

        self.assertEqual(result, False)
        self.check_args("match", "target", "credentials")

    def test_fail_with_exc(self):
        class TestException(Exception):
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        self.fake_brain.check_result = False
        try:
            result = policy.enforce("match", "target", "credentials",
                                    TestException, "arg1", "arg2",
                                    kw1="kwarg1", kw2="kwarg2")
        except TestException as exc:
            self.assertEqual(exc.args, ("arg1", "arg2"))
            self.assertEqual(exc.kwargs, dict(kw1="kwarg1", kw2="kwarg2"))
        else:
            self.fail("policy.enforce() failed to raise requested exception")


class BrainTestCase(unittest.TestCase):
    def test_basic_init(self):
        brain = policy.Brain()

        self.assertEqual(brain.rules, {})
        self.assertEqual(brain.default_rule, None)

    def test_init_with_args(self):
        brain = policy.Brain(rules=dict(a="foo", b="bar"), default_rule="a")

        self.assertEqual(brain.rules, dict(a="foo", b="bar"))
        self.assertEqual(brain.default_rule, "a")

    def test_load_json(self):
        exemplar = """{
    "admin_or_owner": [["role:admin"], ["project_id:%(project_id)s"]],
    "default": []
}"""
        brain = policy.Brain.load_json(exemplar, "default")

        self.assertEqual(
            brain.rules, dict(
                admin_or_owner=[["role:admin"], ["project_id:%(project_id)s"]],
                default=[],
            )
        )
        self.assertEqual(brain.default_rule, "default")

    def test_add_rule(self):
        brain = policy.Brain()
        brain.add_rule("rule1",
                       [["role:admin"], ["project_id:%(project_id)s"]])

        self.assertEqual(
            brain.rules, dict(
                rule1=[["role:admin"], ["project_id:%(project_id)s"]]))

    def test_check_with_badmatch(self):
        brain = policy.Brain()
        result = brain._check("badmatch", "target", "credentials")

        self.assertEqual(result, False)

    def test_check_with_specific(self):
        self.spam_called = False

        class TestBrain(policy.Brain):
            def _check_spam(inst, match, target_dict, cred_dict):
                self.assertEqual(match, "check")
                self.assertEqual(target_dict, "target")
                self.assertEqual(cred_dict, "credentials")
                self.spam_called = True

        brain = TestBrain()
        result = brain._check("spam:check", "target", "credentials")

        self.assertEqual(self.spam_called, True)

    def test_check_with_generic(self):
        self.generic_called = False

        class TestBrain(policy.Brain):
            def _check_generic(inst, match, target_dict, cred_dict):
                self.assertEqual(match, "spam:check")
                self.assertEqual(target_dict, "target")
                self.assertEqual(cred_dict, "credentials")
                self.generic_called = True

        brain = TestBrain()
        result = brain._check("spam:check", "target", "credentials")

        self.assertEqual(self.generic_called, True)

    def test_check_empty(self):
        class TestBrain(policy.Brain):
            def _check(inst, match, target_dict, cred_dict):
                self.fail("_check() called for empty match list!")

        brain = TestBrain()
        result = brain.check([], "target", "credentials")

        self.assertEqual(result, True)

    def stub__check(self):
        self._check_called = 0
        self.matches = []
        self.targets = []
        self.creds = []

        class TestBrain(policy.Brain):
            def _check(inst, match, target_dict, cred_dict):
                self._check_called += 1
                self.matches.append(match)
                self.targets.append(target_dict)
                self.creds.append(cred_dict)
                return match == "True"

        return TestBrain()

    def test_check_basic_true(self):
        brain = self.stub__check()
        result = brain.check(["True"], "target", "creds")

        self.assertEqual(result, True)
        self.assertEqual(self._check_called, 1)
        self.assertEqual(self.matches, ["True"])
        self.assertEqual(self.targets, ["target"])
        self.assertEqual(self.creds, ["creds"])

    def test_check_basic_false(self):
        brain = self.stub__check()
        result = brain.check(["False"], "target", "creds")

        self.assertEqual(result, False)
        self.assertEqual(self._check_called, 1)
        self.assertEqual(self.matches, ["False"])
        self.assertEqual(self.targets, ["target"])
        self.assertEqual(self.creds, ["creds"])

    def test_check_or_true(self):
        brain = self.stub__check()
        result = brain.check([["False"], ["True"], ["False"]],
                             "target", "creds")

        self.assertEqual(result, True)
        self.assertEqual(self._check_called, 2)
        self.assertEqual(self.matches, ["False", "True"])
        self.assertEqual(self.targets, ["target", "target"])
        self.assertEqual(self.creds, ["creds", "creds"])

    def test_check_or_false(self):
        brain = self.stub__check()
        result = brain.check([["False"], ["False"], ["False"]],
                             "target", "creds")

        self.assertEqual(result, False)
        self.assertEqual(self._check_called, 3)
        self.assertEqual(self.matches, ["False", "False", "False"])
        self.assertEqual(self.targets, ["target", "target", "target"])
        self.assertEqual(self.creds, ["creds", "creds", "creds"])

    def test_check_and_true(self):
        brain = self.stub__check()
        result = brain.check([["True", "True", "True"]],
                             "target", "creds")

        self.assertEqual(result, True)
        self.assertEqual(self._check_called, 3)
        self.assertEqual(self.matches, ["True", "True", "True"])
        self.assertEqual(self.targets, ["target", "target", "target"])
        self.assertEqual(self.creds, ["creds", "creds", "creds"])

    def test_check_and_false(self):
        brain = self.stub__check()
        result = brain.check([["True", "True", "False"]],
                             "target", "creds")

        self.assertEqual(result, False)
        self.assertEqual(self._check_called, 3)
        self.assertEqual(self.matches, ["True", "True", "False"])
        self.assertEqual(self.targets, ["target", "target", "target"])
        self.assertEqual(self.creds, ["creds", "creds", "creds"])

    def stub__check_rule(self, rules=None, default_rule=None):
        self.check_called = False

        class TestBrain(policy.Brain):
            def check(inst, matchs, target_dict, cred_dict):
                self.check_called = True
                self.target = target_dict
                self.cred = cred_dict
                return matchs

        return TestBrain(rules=rules, default_rule=default_rule)

    def test_rule_no_rules_no_default(self):
        brain = self.stub__check_rule()
        result = brain._check_rule("spam", "target", "creds")

        self.assertEqual(result, False)
        self.assertEqual(self.check_called, False)

    def test_rule_no_rules_default(self):
        brain = self.stub__check_rule(default_rule="spam")
        result = brain._check_rule("spam", "target", "creds")

        self.assertEqual(result, False)
        self.assertEqual(self.check_called, False)

    def test_rule_no_rules_non_default(self):
        brain = self.stub__check_rule(default_rule="spam")
        result = brain._check_rule("python", "target", "creds")

        self.assertEqual(self.check_called, True)
        self.assertEqual(result, ("rule:spam",))
        self.assertEqual(self.target, "target")
        self.assertEqual(self.cred, "creds")

    def test_rule_with_rules(self):
        brain = self.stub__check_rule(rules=dict(spam=["hiho:ni"]))
        result = brain._check_rule("spam", "target", "creds")

        self.assertEqual(self.check_called, True)
        self.assertEqual(result, ["hiho:ni"])
        self.assertEqual(self.target, "target")
        self.assertEqual(self.cred, "creds")

    def test_role_no_match(self):
        brain = policy.Brain()
        result = brain._check_role("SpAm", {}, dict(roles=["a", "b", "c"]))

        self.assertEqual(result, False)

    def test_role_with_match(self):
        brain = policy.Brain()
        result = brain._check_role("SpAm", {}, dict(roles=["a", "b", "sPaM"]))

        self.assertEqual(result, True)

    def test_generic_no_key(self):
        brain = policy.Brain()
        result = brain._check_generic("tenant:%(tenant_id)s",
                                      dict(tenant_id="spam"),
                                      {})

        self.assertEqual(result, False)

    def test_generic_with_key_mismatch(self):
        brain = policy.Brain()
        result = brain._check_generic("tenant:%(tenant_id)s",
                                      dict(tenant_id="spam"),
                                      dict(tenant="nospam"))

        self.assertEqual(result, False)

    def test_generic_with_key_match(self):
        brain = policy.Brain()
        result = brain._check_generic("tenant:%(tenant_id)s",
                                      dict(tenant_id="spam"),
                                      dict(tenant="spam"))

        self.assertEqual(result, True)


class HttpBrainTestCase(unittest.TestCase):
    def setUp(self):
        self.urlopen_result = ""

        def fake_urlopen(url, post_data):
            self.url = url
            self.post_data = post_data
            return StringIO.StringIO(self.urlopen_result)

        self.patcher = mock.patch.object(urllib2, "urlopen", fake_urlopen)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def decode_post_data(self):
        result = {}
        for item in self.post_data.split('&'):
            key, _sep, value = item.partition('=')
            result[key] = jsonutils.loads(urllib.unquote_plus(value))

        return result

    def test_http_false(self):
        brain = policy.HttpBrain()
        result = brain._check_http("//spam.example.org/%(tenant)s",
                                   dict(tenant="spam"),
                                   dict(roles=["a", "b", "c"]))

        self.assertEqual(result, False)
        self.assertEqual(self.url, "//spam.example.org/spam")
        self.assertEqual(self.decode_post_data(), dict(
                         target=dict(tenant="spam"),
                         credentials=dict(roles=["a", "b", "c"])))

    def test_http_true(self):
        self.urlopen_result = "True"
        brain = policy.HttpBrain()
        result = brain._check_http("//spam.example.org/%(tenant)s",
                                   dict(tenant="spam"),
                                   dict(roles=["a", "b", "c"]))

        self.assertEqual(result, True)
        self.assertEqual(self.url, "//spam.example.org/spam")
        self.assertEqual(self.decode_post_data(), dict(
                         target=dict(tenant="spam"),
                         credentials=dict(roles=["a", "b", "c"])))
