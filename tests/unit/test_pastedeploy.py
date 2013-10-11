# Copyright 2012 Red Hat, Inc.
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
import tempfile

import fixtures

from openstack.common import pastedeploy
from openstack.common import test


class App(object):

    def __init__(self, data):
        self.data = data


class AppWithLocalConf(App):

    def __init__(self, data, foo=None):
        super(AppWithLocalConf, self).__init__(data)
        self.foo = foo


class Filter(object):

    def __init__(self, app, data):
        self.app = app
        self.data = data


class PasteTestCase(test.BaseTestCase):

    def setUp(self):
        super(PasteTestCase, self).setUp()
        self.useFixture(fixtures.NestedTempfile())

    def create_tempfile(self, contents):
        (fd, path) = tempfile.mkstemp()
        try:
            os.write(fd, contents)
        finally:
            os.close(fd)
        return path

    def test_app_factory(self):
        data = 'test_app_factory'

        paste_conf = self.create_tempfile("""[DEFAULT]
[app:myfoo]
paste.app_factory = openstack.common.pastedeploy:app_factory
openstack.app_factory = tests.unit.test_pastedeploy:App
""")

        app = pastedeploy.paste_deploy_app(paste_conf, 'myfoo', data)
        self.assertEqual(app.data, data)

    def test_app_factory_with_local_conf(self):
        data = 'test_app_factory_with_local_conf'

        paste_conf = self.create_tempfile("""[DEFAULT]
[app:myfoo]
paste.app_factory = openstack.common.pastedeploy:app_factory
openstack.app_factory = tests.unit.test_pastedeploy:AppWithLocalConf
foo = bar
""")

        app = pastedeploy.paste_deploy_app(paste_conf, 'myfoo', data)
        self.assertEqual(app.data, data)
        self.assertEqual(app.foo, 'bar')

    def test_filter_factory(self):
        data = 'test_filter_factory'

        paste_conf = self.create_tempfile("""[DEFAULT]
[pipeline:myfoo]
pipeline = myfoofilter myfooapp

[filter:myfoofilter]
paste.filter_factory = openstack.common.pastedeploy:filter_factory
openstack.filter_factory = tests.unit.test_pastedeploy:Filter

[app:myfooapp]
paste.app_factory = openstack.common.pastedeploy:app_factory
openstack.app_factory = tests.unit.test_pastedeploy:App
""")

        app = pastedeploy.paste_deploy_app(paste_conf, 'myfoo', data)
        self.assertEqual(app.data, data)
        self.assertEqual(app.app.data, data)
