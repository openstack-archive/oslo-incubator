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

import os
import socket

import mock
import routes
import six
import webob

from openstack.common.deprecated import wsgi
from openstack.common.fixture import config
from openstack.common.py3kcompat import urlutils
from openstack.common import test

TEST_VAR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                            '..', '..', 'var'))


class RequestTest(test.BaseTestCase):

    def test_content_type_missing(self):
        request = wsgi.Request.blank('/tests/123', method='POST')
        request.body = "<body />"
        self.assertEqual(None, request.get_content_type())

    def test_content_type_unsupported(self):
        request = wsgi.Request.blank('/tests/123', method='POST')
        request.headers["Content-Type"] = "text/html"
        request.body = "asdf<br />"
        self.assertRaises(wsgi.InvalidContentType,
                          request.get_content_type)

    def test_content_type_with_charset(self):
        request = wsgi.Request.blank('/tests/123')
        request.headers["Content-Type"] = "application/json; charset=UTF-8"
        result = request.get_content_type()
        self.assertEqual(result, "application/json")

    def test_content_type_with_given_content_types(self):
        request = wsgi.Request.blank('/tests/123')
        request.headers["Content-Type"] = "application/new-type;"
        result = request.get_content_type(["application/json",
                                           "application/new-type"])
        self.assertEqual(result, "application/new-type")

    def test_content_type_from_accept_xml(self):
        request = wsgi.Request.blank('/tests/123')
        request.headers["Accept"] = "application/xml"
        result = request.best_match_content_type()
        self.assertEqual(result, "application/xml")

        request = wsgi.Request.blank('/tests/123')
        request.headers["Accept"] = "application/json"
        result = request.best_match_content_type()
        self.assertEqual(result, "application/json")

        request = wsgi.Request.blank('/tests/123')
        request.headers["Accept"] = "application/xml, application/json"
        result = request.best_match_content_type()
        self.assertEqual(result, "application/json")

        request = wsgi.Request.blank('/tests/123')
        request.headers["Accept"] = ("application/json; q=0.3, "
                                     "application/xml; q=0.9")
        result = request.best_match_content_type()
        self.assertEqual(result, "application/xml")

    def test_content_type_from_query_extension(self):
        request = wsgi.Request.blank('/tests/123.xml')
        result = request.best_match_content_type()
        self.assertEqual(result, "application/xml")

        request = wsgi.Request.blank('/tests/123.json')
        result = request.best_match_content_type()
        self.assertEqual(result, "application/json")

        request = wsgi.Request.blank('/tests/123.invalid')
        result = request.best_match_content_type()
        self.assertEqual(result, "application/json")

    def test_content_type_accept_and_query_extension(self):
        request = wsgi.Request.blank('/tests/123.xml')
        request.headers["Accept"] = "application/json"
        result = request.best_match_content_type()
        self.assertEqual(result, "application/xml")

    def test_content_type_accept_default(self):
        request = wsgi.Request.blank('/tests/123.unsupported')
        request.headers["Accept"] = "application/unsupported1"
        result = request.best_match_content_type()
        self.assertEqual(result, "application/json")

    def test_content_type_accept_with_given_content_types(self):
        request = wsgi.Request.blank('/tests/123')
        request.headers["Accept"] = "application/new_type"
        result = request.best_match_content_type(["application/new_type"])
        self.assertEqual(result, "application/new_type")


class ActionDispatcherTest(test.BaseTestCase):

    def test_dispatch(self):
        serializer = wsgi.ActionDispatcher()
        serializer.create = lambda x: x
        self.assertEqual(serializer.dispatch('pants', action='create'),
                         'pants')

    def test_dispatch_action_None(self):
        serializer = wsgi.ActionDispatcher()
        serializer.create = lambda x: x + ' pants'
        serializer.default = lambda x: x + ' trousers'
        self.assertEqual(serializer.dispatch('Two', action=None),
                         'Two trousers')

    def test_dispatch_default(self):
        serializer = wsgi.ActionDispatcher()
        serializer.create = lambda x: x + ' pants'
        serializer.default = lambda x: x + ' trousers'
        self.assertEqual(serializer.dispatch('Two', action='update'),
                         'Two trousers')


class ResponseHeadersSerializerTest(test.BaseTestCase):

    def test_default(self):
        serializer = wsgi.ResponseHeadersSerializer()
        response = webob.Response()
        serializer.serialize(response, {'v': '123'}, 'asdf')
        self.assertEqual(response.status_int, 200)

    def test_custom(self):
        class Serializer(wsgi.ResponseHeadersSerializer):
            def update(self, response, data):
                response.status_int = 404
                response.headers['X-Custom-Header'] = data['v']
        serializer = Serializer()
        response = webob.Response()
        serializer.serialize(response, {'v': '123'}, 'update')
        self.assertEqual(response.status_int, 404)
        self.assertEqual(response.headers['X-Custom-Header'], '123')


class DictSerializerTest(test.BaseTestCase):

    def test_dispatch_default(self):
        serializer = wsgi.DictSerializer()
        self.assertEqual(serializer.serialize({}, 'NonExistentAction'), '')


class XMLDictSerializerTest(test.BaseTestCase):

    def test_xml(self):
        input_dict = dict(servers=dict(a=(2, 3)))
        expected_xml = """<servers xmlns="asdf">
                           <a>(2,3)</a>
                         </servers>"""
        serializer = wsgi.XMLDictSerializer(xmlns="asdf")
        result = serializer.serialize(input_dict)
        result = result.replace('\n', '').replace(' ', '')
        expected_xml = expected_xml.replace('\n', '').replace(' ', '')
        self.assertEqual(result, expected_xml)


class JSONDictSerializerTest(test.BaseTestCase):

    def test_json(self):
        input_dict = dict(servers=dict(a=(2, 3)))
        expected_json = '{"servers":{"a":[2,3]}}'
        serializer = wsgi.JSONDictSerializer()
        result = serializer.serialize(input_dict)
        result = result.replace('\n', '').replace(' ', '')
        self.assertEqual(result, expected_json)

    def test_object_unicode(self):
        class TestUnicode:
            def __unicode__(self):
                return six.u('TestUnicode')
        input_dict = dict(cls=TestUnicode())
        expected_str = '{"cls":"TestUnicode"}'
        serializer = wsgi.JSONDictSerializer()
        result = serializer.serialize(input_dict)
        result = result.replace('\n', '').replace(' ', '')
        self.assertEqual(result, expected_str)


class TextDeserializerTest(test.BaseTestCase):

    def test_dispatch_default(self):
        deserializer = wsgi.TextDeserializer()
        self.assertEqual(deserializer.deserialize({}, 'update'), {})


class JSONDeserializerTest(test.BaseTestCase):

    def test_json(self):
        data = """{"a": {
                "a1": "1",
                "a2": "2",
                "bs": ["1", "2", "3", {"c": {"c1": "1"}}],
                "d": {"e": "1"},
                "f": "1"}}"""
        as_dict = {
            'body': {
                'a': {
                    'a1': '1',
                    'a2': '2',
                    'bs': ['1', '2', '3', {'c': {'c1': '1'}}],
                    'd': {'e': '1'},
                    'f': '1',
                },
            },
        }
        deserializer = wsgi.JSONDeserializer()
        self.assertEqual(deserializer.deserialize(data), as_dict)


class XMLDeserializerTest(test.BaseTestCase):

    def test_xml(self):
        xml = """
            <a a1="1" a2="2">
              <bs><b>1</b><b>2</b><b>3</b><b><c c1="1"/></b></bs>
              <d><e>1</e></d>
              <f>1</f>
            </a>
            """.strip()
        as_dict = {
            'body': {
                'a': {
                    'a1': '1',
                    'a2': '2',
                    'bs': ['1', '2', '3', {'c': {'c1': '1'}}],
                    'd': {'e': '1'},
                    'f': '1',
                },
            },
        }
        metadata = {'plurals': {'bs': 'b', 'ts': 't'}}
        deserializer = wsgi.XMLDeserializer(metadata=metadata)
        self.assertEqual(deserializer.deserialize(xml), as_dict)

    def test_xml_empty(self):
        xml = '<a></a>'
        as_dict = {"body": {"a": {}}}
        deserializer = wsgi.XMLDeserializer()
        self.assertEqual(deserializer.deserialize(xml), as_dict)


class RequestHeadersDeserializerTest(test.BaseTestCase):

    def test_default(self):
        deserializer = wsgi.RequestHeadersDeserializer()
        req = wsgi.Request.blank('/')
        self.assertEqual(deserializer.deserialize(req, 'nonExistent'), {})

    def test_custom(self):
        class Deserializer(wsgi.RequestHeadersDeserializer):
            def update(self, request):
                return {'a': request.headers['X-Custom-Header']}
        deserializer = Deserializer()
        req = wsgi.Request.blank('/')
        req.headers['X-Custom-Header'] = 'b'
        self.assertEqual(deserializer.deserialize(req, 'update'), {'a': 'b'})


class ResponseSerializerTest(test.BaseTestCase):

    def setUp(self):
        super(ResponseSerializerTest, self).setUp()

        class JSONSerializer(object):
            def serialize(self, data, action='default'):
                return 'pew_json'

        class XMLSerializer(object):
            def serialize(self, data, action='default'):
                return 'pew_xml'

        class HeadersSerializer(object):
            def serialize(self, response, data, action):
                response.status_int = 404

        self.body_serializers = {
            'application/json': JSONSerializer(),
            'application/xml': XMLSerializer(),
        }

        self.serializer = wsgi.ResponseSerializer(self.body_serializers,
                                                  HeadersSerializer())

    def test_get_serializer(self):
        ctype = 'application/json'
        self.assertEqual(self.serializer.get_body_serializer(ctype),
                         self.body_serializers[ctype])

    def test_get_serializer_unknown_content_type(self):
        self.assertRaises(wsgi.InvalidContentType,
                          self.serializer.get_body_serializer,
                          'application/unknown')

    def test_serialize_json_response(self):
        response = self.serializer.serialize({}, 'application/json')
        self.assertEqual(response.headers['Content-Type'], 'application/json')
        self.assertEqual(response.body, 'pew_json')
        self.assertEqual(response.status_int, 404)

    def test_serialize_xml_response(self):
        response = self.serializer.serialize({}, 'application/xml')
        self.assertEqual(response.headers['Content-Type'], 'application/xml')
        self.assertEqual(response.body, 'pew_xml')
        self.assertEqual(response.status_int, 404)

    def test_serialize_response_None(self):
        response = self.serializer.serialize(None, 'application/json')

        self.assertEqual(response.headers['Content-Type'], 'application/json')
        self.assertEqual(response.body, '')
        self.assertEqual(response.status_int, 404)

    def test_serialize_response_dict_to_unknown_content_type(self):
        self.assertRaises(wsgi.InvalidContentType,
                          self.serializer.serialize,
                          {}, 'application/unknown')


class RequestDeserializerTest(test.BaseTestCase):

    def setUp(self):
        super(RequestDeserializerTest, self).setUp()

        class JSONDeserializer(object):
            def deserialize(self, data, action='default'):
                return 'pew_json'

        class XMLDeserializer(object):
            def deserialize(self, data, action='default'):
                return 'pew_xml'

        self.body_deserializers = {
            'application/json': JSONDeserializer(),
            'application/xml': XMLDeserializer(),
        }

        self.deserializer = wsgi.RequestDeserializer(self.body_deserializers)

    def test_get_deserializer(self):
        expected_json_serializer = self.deserializer.get_body_deserializer(
            'application/json')
        expected_xml_serializer = self.deserializer.get_body_deserializer(
            'application/xml')
        self.assertEqual(expected_json_serializer,
                         self.body_deserializers['application/json'])
        self.assertEqual(expected_xml_serializer,
                         self.body_deserializers['application/xml'])

    def test_get_deserializer_unknown_content_type(self):
        self.assertRaises(wsgi.InvalidContentType,
                          self.deserializer.get_body_deserializer,
                          'application/unknown')

    def test_get_expected_content_type(self):
        request = wsgi.Request.blank('/')
        request.headers['Accept'] = 'application/json'
        self.assertEqual(self.deserializer.get_expected_content_type(request),
                         'application/json')

    def test_get_action_args(self):
        env = {
            'wsgiorg.routing_args': [None, {
                'controller': None,
                'format': None,
                'action': 'update',
                'id': 12,
            }],
        }

        expected = {'action': 'update', 'id': 12}

        self.assertEqual(self.deserializer.get_action_args(env), expected)

    def test_deserialize(self):
        def fake_get_routing_args(request):
            return {'action': 'create'}
        self.deserializer.get_action_args = fake_get_routing_args

        request = wsgi.Request.blank('/')
        request.headers['Accept'] = 'application/xml'

        deserialized = self.deserializer.deserialize(request)
        expected = ('create', {}, 'application/xml')

        self.assertEqual(expected, deserialized)


class ResourceTest(test.BaseTestCase):

    def test_dispatch(self):
        class Controller(object):
            def index(self, req, pants=None):
                return pants

        resource = wsgi.Resource(Controller())
        actual = resource.dispatch(resource.controller,
                                   'index', None, pants='off')
        expected = 'off'
        self.assertEqual(actual, expected)

    def test_dispatch_unknown_controller_action(self):
        class Controller(object):
            def index(self, req, pants=None):
                return pants

        resource = wsgi.Resource(Controller())
        self.assertRaises(AttributeError, resource.dispatch,
                          resource.controller, 'create', None, {})

    def test_malformed_request_body_throws_bad_request(self):
        resource = wsgi.Resource(None)
        request = wsgi.Request.blank(
            "/", body="{mal:formed", method='POST',
            headers={'Content-Type': "application/json"})

        response = resource(request)
        self.assertEqual(response.status, '400 Bad Request')

    def test_wrong_content_type_throws_unsupported_media_type_error(self):
        resource = wsgi.Resource(None)
        request = wsgi.Request.blank("/", body="{some:json}", method='POST',
                                     headers={'Content-Type': "xxx"})

        response = resource(request)
        self.assertEqual(response.status, '415 Unsupported Media Type')


class ServerTest(test.BaseTestCase):

    def test_run_server(self):
        listen_patcher = mock.patch('eventlet.listen')
        server_patcher = mock.patch('eventlet.wsgi.server')

        listen_mock = listen_patcher.start()
        server_mock = server_patcher.start()
        try:
            listen_mock.return_value = mock.sentinel.sock
            wsgi.run_server(mock.sentinel.application, mock.sentinel.port)
            server_mock.assert_called_with(mock.sentinel.sock,
                                           mock.sentinel.application)
        finally:
            listen_patcher.stop()
            server_patcher.stop()

    def test_run_server_with_kwargs(self):
        listen_patcher = mock.patch('eventlet.listen')
        server_patcher = mock.patch('eventlet.wsgi.server')

        listen_mock = listen_patcher.start()
        server_mock = server_patcher.start()
        log_format = '%(client_ip)s'
        try:
            listen_mock.return_value = mock.sentinel.sock
            wsgi.run_server(mock.sentinel.application,
                            mock.sentinel.port,
                            log_format=log_format)
            server_mock.assert_called_with(mock.sentinel.sock,
                                           mock.sentinel.application,
                                           log_format=log_format)
        finally:
            listen_patcher.stop()
            server_patcher.stop()


class WSGIServerTest(test.BaseTestCase):

    def test_pool(self):
        server = wsgi.Service('fake', 9000)
        self.assertTrue(server.tg)
        self.assertTrue(server.tg.pool)
        self.assertEqual(server.tg.pool.free(), 1000)

    def test_start_random_port(self):
        server = wsgi.Service('test_random_port', 0)
        server.start()
        self.assertEqual("0.0.0.0", server.host)
        self.assertNotEqual(0, server.port)
        server.stop()

    def test_start_random_port_with_ipv6(self):
        server = wsgi.Service('test_random_port', 0, host="::1")
        server.start()
        self.assertEqual("::1", server.host)
        self.assertNotEqual(0, server.port)
        server.stop()

    def test_app(self):
        greetings = 'Hello, World!!!'

        def hello_world(env, start_response):
            if env['PATH_INFO'] != '/':
                start_response('404 Not Found',
                               [('Content-Type', 'text/plain')])
                return ['Not Found\r\n']
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [greetings]

        server = wsgi.Service(hello_world, 0)
        server.start()

        response = urlutils.urlopen('http://127.0.0.1:%d/' % server.port)
        self.assertEqual(greetings, response.read())

        server.stop()

    def test_app_using_router(self):
        greetings = 'Hello, World!!!'

        @webob.dec.wsgify
        def hello(req):
            return greetings

        mapper = routes.Mapper()
        mapper.connect(None, "/v1.0/{path_info:.*}", controller=hello)
        router = wsgi.Router(mapper)
        server = wsgi.Service(router, 0)
        server.start()

        response = urlutils.urlopen('http://127.0.0.1:%d/v1.0/' % server.port)
        self.assertEqual(greetings, response.read())

        server.stop()

    def test_ipv6_listen_called_with_scope(self):
        with mock.patch.object(wsgi.eventlet, 'listen') as mock_listen:
            with mock.patch.object(socket, 'getaddrinfo') as mock_get_addr:
                mock_get_addr.return_value = [
                    (socket.AF_INET6,
                     socket.SOCK_STREAM,
                     socket.IPPROTO_TCP,
                     '',
                     ('fe80::204:acff:fe96:da87%eth0', 1234, 0, 2))
                ]

                wsgi.Service("test_app",
                             1234,
                             host="fe80::204:acff:fe96:da87%eth0")

                mock_get_addr.assert_called_once_with(
                    "fe80::204:acff:fe96:da87%eth0",
                    1234,
                    socket.AF_UNSPEC,
                    socket.SOCK_STREAM
                )

                mock_listen.assert_called_once_with(
                    ('fe80::204:acff:fe96:da87%eth0', 1234, 0, 2),
                    backlog=4096,
                    family=socket.AF_INET6
                )


class WSGIServerWithSSLTest(test.BaseTestCase):

    def setUp(self):
        super(WSGIServerWithSSLTest, self).setUp()
        self.config = self.useFixture(config.Config()).config

    def test_app_using_router_ssl(self):
        self.config(cert_file=os.path.join(TEST_VAR_DIR, 'certificate.crt'),
                    group="ssl")
        self.config(key_file=os.path.join(TEST_VAR_DIR, 'privatekey.key'),
                    group="ssl")

        greetings = 'Hello, World!!!'

        @webob.dec.wsgify
        def hello(req):
            return greetings

        mapper = routes.Mapper()
        mapper.connect(None, "/v1.0/{path_info:.*}", controller=hello)
        router = wsgi.Router(mapper)
        server = wsgi.Service(router, 0, host="127.0.0.1")
        server.start()

        response = urlutils.urlopen('https://127.0.0.1:%d/v1.0/' % server.port)
        self.assertEqual(greetings, response.read())

        server.stop()

    def test_app_using_router_ipv6_and_ssl(self):
        self.config(cert_file=os.path.join(TEST_VAR_DIR, 'certificate.crt'),
                    group="ssl")
        self.config(key_file=os.path.join(TEST_VAR_DIR, 'privatekey.key'),
                    group="ssl")

        greetings = 'Hello, World!!!'

        @webob.dec.wsgify
        def hello(req):
            return greetings

        mapper = routes.Mapper()
        mapper.connect(None, "/v1.0/{path_info:.*}", controller=hello)
        router = wsgi.Router(mapper)
        server = wsgi.Service(router, 0, host="::1")
        server.start()

        response = urlutils.urlopen('https://[::1]:%d/v1.0/' % server.port)
        self.assertEqual(greetings, response.read())

        server.stop()
