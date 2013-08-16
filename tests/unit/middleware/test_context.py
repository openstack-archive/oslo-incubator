# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack Foundation.
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

import mock

import openstack.common.context

from openstack.common.middleware import context
from openstack.common import test


class ContextMiddlewareTest(test.BaseTestCase):

    def test_process_request(self):
        req = mock.Mock()
        app = mock.Mock()
        options = mock.MagicMock()
        ctx = mock.sentinel.context
        with mock.patch.object(context.ContextMiddleware,
                               'make_context',
                               mock.Mock(return_value=ctx)):
            ctx_middleware = context.ContextMiddleware(app, options)
            ctx_middleware.process_request(req)

        self.assertEqual(req.context, ctx)

    def test_make_context(self):
        app = mock.Mock()
        options = mock.MagicMock()
        with mock.patch.object(openstack.common.context.RequestContext,
                               '__init__',
                               mock.Mock(return_value=None)) as init:
            ctx_middleware = context.ContextMiddleware(app, options)
            ctx_middleware.make_context(mock.sentinel.arg)
            init.assert_called_with(mock.sentinel.arg)

    def test_make_explicit_context(self):
        app = mock.Mock()
        import_class = mock.Mock()
        options = {'context_class': mock.sentinel.context_class}
        with mock.patch('openstack.common.importutils.import_class',
                        mock.Mock(return_value=import_class)):
            ctx_middleware = context.ContextMiddleware(app, options)
            ctx_middleware.make_context(mock.sentinel.arg)
            import_class.assert_called_with(mock.sentinel.arg)


class FilterFactoryTest(test.BaseTestCase):

    def test_filter_factory(self):
        global_conf = dict(sentinel=mock.sentinel.global_conf)
        app = mock.sentinel.app
        target = 'openstack.common.middleware.context.ContextMiddleware'

        def check_ctx_middleware(arg_app, arg_conf):
            self.assertEqual(app, arg_app)
            self.assertEqual(global_conf['sentinel'], arg_conf['sentinel'])
            return mock.DEFAULT

        with mock.patch(target,
                        mock.Mock(return_value=mock.sentinel.ctx)) as mid:
            mid.side_effect = check_ctx_middleware
            filter = context.filter_factory(global_conf)
            self.assertEqual(filter(app), mock.sentinel.ctx)
