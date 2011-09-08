# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright 2011 OpenStack LLC.
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

import json
from lxml import etree
import os.path
import routes
import unittest

from webtest import TestApp


from openstack.common import wsgi
from openstack.common import config
from openstack.common import extensions
from tests.unit.extension_stubs import (StubExtension,
                                        StubBaseAppController)
from openstack.common.extensions import (ExtensionManager,
                                       ExtensionMiddleware)


test_conf_file = os.path.join(os.path.dirname(__file__), os.pardir,
                              os.pardir, 'etc', 'openstack-common.conf.test')
extensions_path = os.path.join(os.path.dirname(__file__), "extensions")

NS = "{http://docs.openstack.org/}"
ATOMNS = "{http://www.w3.org/2005/Atom}"


class ExtensionsTestApp(wsgi.Router):

    def __init__(self, options={}):
        mapper = routes.Mapper()
        controller = StubBaseAppController()
        mapper.resource("dummy_resource", "/dummy_resources",
                        controller=controller.create_resource())
        super(ExtensionsTestApp, self).__init__(mapper)


class ResourceExtensionTest(unittest.TestCase):

    class ResourceExtensionController(object):

        def index(self, request):
            return "resource index"

        def show(self, request, id):
            return {'data': {'id': id}}

        def custom_member_action(self, request, id):
            return {'member_action': 'value'}

        def custom_collection_action(self, request, **kwargs):
            return {'collection': 'value'}

    def test_resource_can_be_added_as_extension(self):
        res_ext = extensions.ResourceExtension('tweedles',
                                            self.ResourceExtensionController())
        test_app = setup_extensions_test_app(SimpleExtensionManager(res_ext))

        index_response = test_app.get("/tweedles")
        self.assertEqual(200, index_response.status_int)
        self.assertEqual("resource index", index_response.json)

        show_response = test_app.get("/tweedles/25266")
        self.assertEqual({'data': {'id': "25266"}}, show_response.json)

    def test_resource_extension_with_custom_member_action(self):
        controller = self.ResourceExtensionController()
        member = {'custom_member_action': "GET"}
        res_ext = extensions.ResourceExtension('tweedles', controller,
                                               member_actions=member)
        test_app = setup_extensions_test_app(SimpleExtensionManager(res_ext))

        response = test_app.get("/tweedles/some_id/custom_member_action")
        self.assertEqual(200, response.status_int)
        self.assertEqual(json.loads(response.body)['member_action'], "value")

    def test_resource_extension_for_get_custom_collection_action(self):
        controller = self.ResourceExtensionController()
        collections = {'custom_collection_action': "PUT"}
        res_ext = extensions.ResourceExtension('tweedles', controller,
                                               collection_actions=collections)
        test_app = setup_extensions_test_app(SimpleExtensionManager(res_ext))

        response = test_app.put("/tweedles/custom_collection_action")
        self.assertEqual(200, response.status_int)
        self.assertEqual(json.loads(response.body)['collection'], "value")

    def test_resource_extension_for_put_custom_collection_action(self):
        controller = self.ResourceExtensionController()
        collections = {'custom_collection_action': "PUT"}
        res_ext = extensions.ResourceExtension('tweedles', controller,
                                               collection_actions=collections)
        test_app = setup_extensions_test_app(SimpleExtensionManager(res_ext))

        response = test_app.put("/tweedles/custom_collection_action")

        self.assertEqual(200, response.status_int)
        self.assertEqual(json.loads(response.body)['collection'], 'value')

    def test_resource_extension_for_post_custom_collection_action(self):
        controller = self.ResourceExtensionController()
        collections = {'custom_collection_action': "POST"}
        res_ext = extensions.ResourceExtension('tweedles', controller,
                                               collection_actions=collections)
        test_app = setup_extensions_test_app(SimpleExtensionManager(res_ext))

        response = test_app.post("/tweedles/custom_collection_action")

        self.assertEqual(200, response.status_int)
        self.assertEqual(json.loads(response.body)['collection'], 'value')

    def test_resource_extension_for_delete_custom_collection_action(self):
        controller = self.ResourceExtensionController()
        collections = {'custom_collection_action': "DELETE"}
        res_ext = extensions.ResourceExtension('tweedles', controller,
                                               collection_actions=collections)
        test_app = setup_extensions_test_app(SimpleExtensionManager(res_ext))

        response = test_app.delete("/tweedles/custom_collection_action")

        self.assertEqual(200, response.status_int)
        self.assertEqual(json.loads(response.body)['collection'], 'value')

    def test_resource_ext_for_formatted_req_on_custom_collection_action(self):
        controller = self.ResourceExtensionController()
        collections = {'custom_collection_action': "GET"}
        res_ext = extensions.ResourceExtension('tweedles', controller,
                                               collection_actions=collections)
        test_app = setup_extensions_test_app(SimpleExtensionManager(res_ext))

        response = test_app.get("/tweedles/custom_collection_action.json")

        self.assertEqual(200, response.status_int)
        self.assertEqual(json.loads(response.body)['collection'], "value")

    def test_resource_ext_for_nested_resource_custom_collection_action(self):
        controller = self.ResourceExtensionController()
        collections = {'custom_collection_action': "GET"}
        parent = dict(collection_name='beetles', member_name='beetle')
        res_ext = extensions.ResourceExtension('tweedles', controller,
                                               collection_actions=collections,
                                               parent=parent)
        test_app = setup_extensions_test_app(SimpleExtensionManager(res_ext))

        response = test_app.get("/beetles/beetle_id"
                                "/tweedles/custom_collection_action")

        self.assertEqual(200, response.status_int)
        self.assertEqual(json.loads(response.body)['collection'], "value")

    def test_returns_404_for_non_existant_extension(self):
        test_app = setup_extensions_test_app(SimpleExtensionManager(None))

        response = test_app.get("/non_extistant_extension", status='*')

        self.assertEqual(404, response.status_int)


class ActionExtensionTest(unittest.TestCase):

    def setUp(self):
        super(ActionExtensionTest, self).setUp()
        self.extension_app = setup_extensions_test_app()

    def test_extended_action_for_adding_extra_data(self):
        action_name = 'FOXNSOX:add_tweedle'
        action_params = dict(name='Beetle')
        req_body = json.dumps({action_name: action_params})
        response = self.extension_app.post('/dummy_resources/1/action',
                                     req_body, content_type='application/json')

        self.assertEqual("Tweedle Beetle Added.", response.json)

    def test_extended_action_for_deleting_extra_data(self):
        action_name = 'FOXNSOX:delete_tweedle'
        action_params = dict(name='Bailey')
        req_body = json.dumps({action_name: action_params})
        response = self.extension_app.post("/dummy_resources/1/action",
                                     req_body, content_type='application/json')
        self.assertEqual("Tweedle Bailey Deleted.", response.json)

    def test_returns_404_for_non_existant_action(self):
        non_existant_action = 'blah_action'
        action_params = dict(name="test")
        req_body = json.dumps({non_existant_action: action_params})

        response = self.extension_app.post("/dummy_resources/1/action",
                                     req_body, content_type='application/json',
                                     status='*')

        self.assertEqual(404, response.status_int)

    def test_returns_404_for_non_existant_resource(self):
        action_name = 'add_tweedle'
        action_params = dict(name='Beetle')
        req_body = json.dumps({action_name: action_params})

        response = self.extension_app.post("/asdf/1/action", req_body,
                                   content_type='application/json', status='*')
        self.assertEqual(404, response.status_int)


class RequestExtensionTest(unittest.TestCase):

    def test_headers_can_be_extended(self):
        def extend_headers(req, res):
            assert req.headers['X-NEW-REQUEST-HEADER'] == "sox"
            res.headers['X-NEW-RESPONSE-HEADER'] = "response_header_data"
            return res

        app = self._setup_app_with_request_handler(extend_headers, 'GET')
        response = app.get("/dummy_resources/1",
                           headers={'X-NEW-REQUEST-HEADER': "sox"})

        self.assertEqual(response.headers['X-NEW-RESPONSE-HEADER'],
                                                   "response_header_data")

    def test_extend_get_resource_response(self):
        def extend_response_data(req, res):
            data = json.loads(res.body)
            data['FOXNSOX:extended_key'] = req.GET.get('extended_key')
            res.body = json.dumps(data)
            return res

        app = self._setup_app_with_request_handler(extend_response_data, 'GET')
        response = app.get("/dummy_resources/1?extended_key=extended_data")

        self.assertEqual(200, response.status_int)

        response_data = json.loads(response.body)
        self.assertEqual('extended_data',
                         response_data['FOXNSOX:extended_key'])
        self.assertEqual('knox', response_data['fort'])

    def test_get_resources(self):
        app = setup_extensions_test_app()

        response = app.get("/dummy_resources/1?chewing=newblue")

        response_data = json.loads(response.body)
        self.assertEqual('newblue', response_data['FOXNSOX:googoose'])
        self.assertEqual("Pig Bands!", response_data['FOXNSOX:big_bands'])

    def test_edit_previously_uneditable_field(self):

        def _update_handler(req, res):
            data = json.loads(res.body)
            data['uneditable'] = json.loads(req.body)['uneditable']
            res.body = json.dumps(data)
            return res

        base_app = TestApp(setup_base_app())
        response = base_app.put("/dummy_resources/1",
                                json.dumps({'uneditable': "new_value"}),
                                headers={'Content-Type': "application/json"})
        self.assertEqual(response.json['uneditable'], "original_value")

        ext_app = self._setup_app_with_request_handler(_update_handler,
                                                            'PUT')
        ext_response = ext_app.put("/dummy_resources/1",
                                  json.dumps({'uneditable': "new_value"}),
                                  headers={'Content-Type': "application/json"})
        self.assertEqual(ext_response.json['uneditable'], "new_value")

    def _setup_app_with_request_handler(self, handler, verb):
        req_ext = extensions.RequestExtension(verb,
                                   '/dummy_resources/:(id)', handler)
        manager = SimpleExtensionManager(None, None, req_ext)
        return setup_extensions_test_app(manager)


class ExtensionManagerTest(unittest.TestCase):

    def test_invalid_extensions_are_not_registered(self):

        class InvalidExtension(object):
            """
            This Extension doesn't implement extension methods :
            get_name, get_description, get_namespace and get_updated
            """
            def get_alias(self):
                return "invalid_extension"

        ext_mgr = ExtensionManager('')
        ext_mgr.add_extension(InvalidExtension())
        ext_mgr.add_extension(StubExtension("valid_extension"))

        self.assertTrue('valid_extension' in ext_mgr.extensions)
        self.assertFalse('invalid_extension' in ext_mgr.extensions)


class ExtensionControllerTest(unittest.TestCase):

    def setUp(self):
        super(ExtensionControllerTest, self).setUp()
        self.test_app = setup_extensions_test_app()

    def test_index_gets_all_registerd_extensions(self):
        response = self.test_app.get("/extensions")
        foxnsox = response.json["extensions"][0]

        self.assertEqual(foxnsox, {
                'namespace': 'http://www.fox.in.socks/api/ext/pie/v1.0',
                'name': 'Fox In Socks',
                'updated': '2011-01-22T13:25:27-06:00',
                'description': 'The Fox In Socks Extension',
                'alias': 'FOXNSOX',
                'links': []
            }
        )

    def test_extension_can_be_accessed_by_alias(self):
        json_response = self.test_app.get("/extensions/FOXNSOX").json
        foxnsox = json_response['extension']

        self.assertEqual(foxnsox, {
                'namespace': 'http://www.fox.in.socks/api/ext/pie/v1.0',
                'name': 'Fox In Socks',
                'updated': '2011-01-22T13:25:27-06:00',
                'description': 'The Fox In Socks Extension',
                'alias': 'FOXNSOX',
                'links': []
            }
        )

    def test_show_returns_not_found_for_non_existant_extension(self):
        response = self.test_app.get("/extensions/non_existant", status="*")

        self.assertEqual(response.status_int, 404)

    def test_list_extensions_xml(self):
        response = self.test_app.get("/extensions.xml")

        self.assertEqual(200, response.status_int)
        root = etree.XML(response.body)
        self.assertEqual(root.tag.split('extensions')[0], NS)

        # Make sure that Fox in Sox extension is correct.
        exts = root.findall('{0}extension'.format(NS))
        fox_ext = exts[0]
        self.assertEqual(fox_ext.get('name'), 'Fox In Socks')
        self.assertEqual(fox_ext.get('namespace'),
            'http://www.fox.in.socks/api/ext/pie/v1.0')
        self.assertEqual(fox_ext.get('updated'), '2011-01-22T13:25:27-06:00')
        self.assertEqual(fox_ext.findtext('{0}description'.format(NS)),
            'The Fox In Socks Extension')

    def test_get_extension_xml(self):
        response = self.test_app.get("/extensions/FOXNSOX.xml")
        self.assertEqual(200, response.status_int)
        xml = response.body

        root = etree.XML(xml)
        self.assertEqual(root.tag.split('extension')[0], NS)
        self.assertEqual(root.get('alias'), 'FOXNSOX')
        self.assertEqual(root.get('name'), 'Fox In Socks')
        self.assertEqual(root.get('namespace'),
            'http://www.fox.in.socks/api/ext/pie/v1.0')
        self.assertEqual(root.get('updated'), '2011-01-22T13:25:27-06:00')
        self.assertEqual(root.findtext('{0}description'.format(NS)),
            'The Fox In Socks Extension')


class ExtensionsXMLSerializerTest(unittest.TestCase):

    def test_serialize_extenstion(self):
        serializer = extensions.ExtensionsXMLSerializer()
        data = {'extension': {
          'name': 'ext1',
          'namespace': 'http://docs.rack.com/servers/api/ext/pie/v1.0',
          'alias': 'RS-PIE',
          'updated': '2011-01-22T13:25:27-06:00',
          'description': 'Adds the capability to share an image.',
          'links': [{'rel': 'describedby',
                     'type': 'application/pdf',
                     'href': 'http://docs.rack.com/servers/api/ext/cs.pdf'},
                    {'rel': 'describedby',
                     'type': 'application/vnd.sun.wadl+xml',
                     'href': 'http://docs.rack.com/servers/api/ext/cs.wadl'}]}}

        xml = serializer.serialize(data, 'show')
        root = etree.XML(xml)
        ext_dict = data['extension']
        self.assertEqual(root.findtext('{0}description'.format(NS)),
            ext_dict['description'])

        for key in ['name', 'namespace', 'alias', 'updated']:
            self.assertEqual(root.get(key), ext_dict[key])

        link_nodes = root.findall('{0}link'.format(ATOMNS))
        self.assertEqual(len(link_nodes), 2)
        for i, link in enumerate(ext_dict['links']):
            for key, value in link.items():
                self.assertEqual(link_nodes[i].get(key), value)

    def test_serialize_extensions(self):
        serializer = extensions.ExtensionsXMLSerializer()
        data = {"extensions": [{
                "name": "Public Image Extension",
                "namespace": "http://foo.com/api/ext/pie/v1.0",
                "alias": "RS-PIE",
                "updated": "2011-01-22T13:25:27-06:00",
                "description": "Adds the capability to share an image.",
                "links": [{"rel": "describedby",
                            "type": "application/pdf",
                            "type": "application/vnd.sun.wadl+xml",
                            "href": "http://foo.com/api/ext/cs-pie.pdf"},
                           {"rel": "describedby",
                            "type": "application/vnd.sun.wadl+xml",
                            "href": "http://foo.com/api/ext/cs-pie.wadl"}]},
                {"name": "Cloud Block Storage",
                 "namespace": "http://foo.com/api/ext/cbs/v1.0",
                 "alias": "RS-CBS",
                 "updated": "2011-01-12T11:22:33-06:00",
                 "description": "Allows mounting cloud block storage.",
                 "links": [{"rel": "describedby",
                             "type": "application/pdf",
                             "href": "http://foo.com/api/ext/cs-cbs.pdf"},
                            {"rel": "describedby",
                             "type": "application/vnd.sun.wadl+xml",
                             "href": "http://foo.com/api/ext/cs-cbs.wadl"}]}]}

        xml = serializer.serialize(data, 'index')
        root = etree.XML(xml)
        ext_elems = root.findall('{0}extension'.format(NS))
        self.assertEqual(len(ext_elems), 2)
        for i, ext_elem in enumerate(ext_elems):
            ext_dict = data['extensions'][i]
            self.assertEqual(ext_elem.findtext('{0}description'.format(NS)),
                             ext_dict['description'])

            for key in ['name', 'namespace', 'alias', 'updated']:
                self.assertEqual(ext_elem.get(key), ext_dict[key])

            link_nodes = ext_elem.findall('{0}link'.format(ATOMNS))
            self.assertEqual(len(link_nodes), 2)
            for i, link in enumerate(ext_dict['links']):
                for key, value in link.items():
                    self.assertEqual(link_nodes[i].get(key), value)


def app_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)
    return ExtensionsTestApp(conf)


def setup_base_app():
    options = {'config_file': test_conf_file}
    conf, app = config.load_paste_app('extensions_test_app', options, None)
    return app


def setup_extensions_middleware(extension_manager=None):
    extension_manager = (extension_manager or
                         ExtensionManager(extensions_path))
    options = {'config_file': test_conf_file}
    conf, app = config.load_paste_app('extensions_test_app', options, None)
    return ExtensionMiddleware(app, extension_manager)


def setup_extensions_test_app(extension_manager=None):
    return TestApp(setup_extensions_middleware(extension_manager))


class SimpleExtensionManager(object):

    def __init__(self, resource_ext=None, action_ext=None, request_ext=None):
        self.resource_ext = resource_ext
        self.action_ext = action_ext
        self.request_ext = request_ext

    def get_resources(self):
        resource_exts = []
        if self.resource_ext:
            resource_exts.append(self.resource_ext)
        return resource_exts

    def get_actions(self):
        action_exts = []
        if self.action_ext:
            action_exts.append(self.action_ext)
        return action_exts

    def get_request_extensions(self):
        request_extensions = []
        if self.request_ext:
            request_extensions.append(self.request_ext)
        return request_extensions
