# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack Foundation
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


import datetime
import filecmp
import os
import random
import tempfile
import time

import glanceclient.exc
from oslo.config import cfg

from openstack.common import context
from openstack.common import exception
from openstack.common.image import glance
from tests.unit.image import fakes
from tests.unit.glance import stubs as glance_stubs
from tests  import utils
from tests.unit.image import matchers

CONF = cfg.CONF


class NullWriter(object):
    """Used to test ImageService.get which takes a writer object."""

    def write(self, *arg, **kwargs):
        pass


class TestGlanceSerializer(utils.BaseTestCase):
    def test_serialize(self):
        metadata = {'name': 'image1',
                    'is_public': True,
                    'foo': 'bar',
                    'properties': {
                        'prop1': 'propvalue1',
                        'mappings': [
                            {'virtual': 'aaa',
                             'device': 'bbb'},
                            {'virtual': 'xxx',
                             'device': 'yyy'}],
                        'block_device_mapping': [
                            {'virtual_device': 'fake',
                             'device_name': '/dev/fake'},
                            {'virtual_device': 'ephemeral0',
                             'device_name': '/dev/fake0'}]}}

        converted_expected = {
            'name': 'image1',
            'is_public': True,
            'foo': 'bar',
            'properties': {
                'prop1': 'propvalue1',
                'mappings':
                '[{"device": "bbb", "virtual": "aaa"}, '
                '{"device": "yyy", "virtual": "xxx"}]',
                'block_device_mapping':
                '[{"virtual_device": "fake", "device_name": "/dev/fake"}, '
                '{"virtual_device": "ephemeral0", '
                '"device_name": "/dev/fake0"}]'}}
        converted = glance._convert_to_string(metadata)
        self.assertEqual(converted, converted_expected)
        self.assertEqual(glance._convert_from_string(converted), metadata)


class TestGlanceImageService(utils.BaseTestCase):
    """
    Tests the Glance image service.

    At a high level, the translations involved are:

        1. Glance -> ImageService - This is needed so we can support
           multple ImageServices (Glance, Local, etc)

        2. ImageService -> API - This is needed so we can support multple
           APIs (OpenStack, EC2)

    """
    NOW_GLANCE_OLD_FORMAT = "2010-10-11T10:30:22"
    NOW_GLANCE_FORMAT = "2010-10-11T10:30:22.000000"

    class tzinfo(datetime.tzinfo):
        @staticmethod
        def utcoffset(*args, **kwargs):
            return datetime.timedelta()

    NOW_DATETIME = datetime.datetime(2010, 10, 11, 10, 30, 22, tzinfo=tzinfo())

    def setUp(self):
        super(TestGlanceImageService, self).setUp()
        fakes.stub_out_compute_api_snapshot(self.stubs)

        client = glance_stubs.StubGlanceClient()
        self.service = self._create_image_service(client)
        self.context = context.RequestContext(auth_token=True)
        self.context.user_id = 'fake'
        self.context.project_id = 'fake'

    def _create_image_service(self, client):
        def _fake_create_glance_client(context, host, port, use_ssl, version):
            return client

        self.stubs.Set(glance, '_create_glance_client',
                _fake_create_glance_client)

        client_wrapper = glance.GlanceClientWrapper(
                'fake', 'fake_host', 9292)
        return glance.GlanceImageService(client=client_wrapper)

    @staticmethod
    def _make_fixture(**kwargs):
        fixture = {'name': None,
                   'properties': {},
                   'status': None,
                   'is_public': None}
        fixture.update(kwargs)
        return fixture

    def _make_datetime_fixture(self):
        return self._make_fixture(created_at=self.NOW_GLANCE_FORMAT,
                                  updated_at=self.NOW_GLANCE_FORMAT,
                                  deleted_at=self.NOW_GLANCE_FORMAT)

    def test_create_with_instance_id(self):
        # Ensure instance_id is persisted as an image-property.
        fixture = {'name': 'test image',
                   'is_public': False,
                   'properties': {'instance_id': '42', 'user_id': 'fake'}}

        image_id = self.service.create(self.context, fixture)['id']
        image_meta = self.service.show(self.context, image_id)
        expected = {
            'id': image_id,
            'name': 'test image',
            'is_public': False,
            'size': None,
            'min_disk': None,
            'min_ram': None,
            'disk_format': None,
            'container_format': None,
            'checksum': None,
            'created_at': self.NOW_DATETIME,
            'updated_at': self.NOW_DATETIME,
            'deleted_at': None,
            'deleted': None,
            'status': None,
            'properties': {'instance_id': '42', 'user_id': 'fake'},
            'owner': None,
        }
        self.assertThat(image_meta, matchers.DictMatches(expected))

        image_metas = self.service.detail(self.context)
        self.assertThat(image_metas[0], matchers.DictMatches(expected))

    def test_create_without_instance_id(self):
        """
        Ensure we can create an image without having to specify an
        instance_id. Public images are an example of an image not tied to an
        instance.
        """
        fixture = {'name': 'test image', 'is_public': False}
        image_id = self.service.create(self.context, fixture)['id']

        expected = {
            'id': image_id,
            'name': 'test image',
            'is_public': False,
            'size': None,
            'min_disk': None,
            'min_ram': None,
            'disk_format': None,
            'container_format': None,
            'checksum': None,
            'created_at': self.NOW_DATETIME,
            'updated_at': self.NOW_DATETIME,
            'deleted_at': None,
            'deleted': None,
            'status': None,
            'properties': {},
            'owner': None,
        }
        actual = self.service.show(self.context, image_id)
        self.assertThat(actual, matchers.DictMatches(expected))

    def test_create(self):
        fixture = self._make_fixture(name='test image')
        num_images = len(self.service.detail(self.context))
        image_id = self.service.create(self.context, fixture)['id']

        self.assertNotEquals(None, image_id)
        self.assertEquals(num_images + 1,
                          len(self.service.detail(self.context)))

    def test_create_and_show_non_existing_image(self):
        fixture = self._make_fixture(name='test image')
        image_id = self.service.create(self.context, fixture)['id']

        self.assertNotEquals(None, image_id)
        self.assertRaises(exception.ImageNotFound,
                          self.service.show,
                          self.context,
                          'bad image id')

    def test_detail_private_image(self):
        fixture = self._make_fixture(name='test image')
        fixture['is_public'] = False
        properties = {'owner_id': 'proj1'}
        fixture['properties'] = properties

        self.service.create(self.context, fixture)['id']

        proj = self.context.project_id
        self.context.project_id = 'proj1'

        image_metas = self.service.detail(self.context)

        self.context.project_id = proj

        self.assertEqual(1, len(image_metas))
        self.assertEqual(image_metas[0]['name'], 'test image')
        self.assertEqual(image_metas[0]['is_public'], False)

    def test_detail_marker(self):
        fixtures = []
        ids = []
        for i in range(10):
            fixture = self._make_fixture(name='TestImage %d' % (i))
            fixtures.append(fixture)
            ids.append(self.service.create(self.context, fixture)['id'])

        image_metas = self.service.detail(self.context, marker=ids[1])
        self.assertEquals(len(image_metas), 8)
        i = 2
        for meta in image_metas:
            expected = {
                'id': ids[i],
                'status': None,
                'is_public': None,
                'name': 'TestImage %d' % (i),
                'properties': {},
                'size': None,
                'min_disk': None,
                'min_ram': None,
                'disk_format': None,
                'container_format': None,
                'checksum': None,
                'created_at': self.NOW_DATETIME,
                'updated_at': self.NOW_DATETIME,
                'deleted_at': None,
                'deleted': None,
                'owner': None,
            }

            self.assertThat(meta, matchers.DictMatches(expected))
            i = i + 1

    def test_detail_limit(self):
        fixtures = []
        ids = []
        for i in range(10):
            fixture = self._make_fixture(name='TestImage %d' % (i))
            fixtures.append(fixture)
            ids.append(self.service.create(self.context, fixture)['id'])

        image_metas = self.service.detail(self.context, limit=5)
        self.assertEquals(len(image_metas), 5)

    def test_detail_default_limit(self):
        fixtures = []
        ids = []
        for i in range(10):
            fixture = self._make_fixture(name='TestImage %d' % (i))
            fixtures.append(fixture)
            ids.append(self.service.create(self.context, fixture)['id'])

        image_metas = self.service.detail(self.context)
        for i, meta in enumerate(image_metas):
            self.assertEqual(meta['name'], 'TestImage %d' % (i))

    def test_detail_marker_and_limit(self):
        fixtures = []
        ids = []
        for i in range(10):
            fixture = self._make_fixture(name='TestImage %d' % (i))
            fixtures.append(fixture)
            ids.append(self.service.create(self.context, fixture)['id'])

        image_metas = self.service.detail(self.context, marker=ids[3], limit=5)
        self.assertEquals(len(image_metas), 5)
        i = 4
        for meta in image_metas:
            expected = {
                'id': ids[i],
                'status': None,
                'is_public': None,
                'name': 'TestImage %d' % (i),
                'properties': {},
                'size': None,
                'min_disk': None,
                'min_ram': None,
                'disk_format': None,
                'container_format': None,
                'checksum': None,
                'created_at': self.NOW_DATETIME,
                'updated_at': self.NOW_DATETIME,
                'deleted_at': None,
                'deleted': None,
                'owner': None,
            }
            self.assertThat(meta, matchers.DictMatches(expected))
            i = i + 1

    def test_detail_invalid_marker(self):
        fixtures = []
        ids = []
        for i in range(10):
            fixture = self._make_fixture(name='TestImage %d' % (i))
            fixtures.append(fixture)
            ids.append(self.service.create(self.context, fixture)['id'])

        self.assertRaises(exception.Invalid, self.service.detail,
                          self.context, marker='invalidmarker')

    def test_update(self):
        fixture = self._make_fixture(name='test image')
        image = self.service.create(self.context, fixture)
        image_id = image['id']
        fixture['name'] = 'new image name'
        self.service.update(self.context, image_id, fixture)

        new_image_data = self.service.show(self.context, image_id)
        self.assertEquals('new image name', new_image_data['name'])

    def test_delete(self):
        fixture1 = self._make_fixture(name='test image 1')
        fixture2 = self._make_fixture(name='test image 2')
        fixtures = [fixture1, fixture2]

        num_images = len(self.service.detail(self.context))
        self.assertEquals(0, num_images)

        ids = []
        for fixture in fixtures:
            new_id = self.service.create(self.context, fixture)['id']
            ids.append(new_id)

        num_images = len(self.service.detail(self.context))
        self.assertEquals(2, num_images)

        self.service.delete(self.context, ids[0])
        # When you delete an image from glance, it sets the status to DELETED
        # and doesn't actually remove the image.

        # Check the image is still there.
        num_images = len(self.service.detail(self.context))
        self.assertEquals(2, num_images)

        # Check the image is marked as deleted.
        num_images = reduce(lambda x, y: x + (0 if y['deleted'] else 1),
                            self.service.detail(self.context), 0)
        self.assertEquals(1, num_images)

    def test_show_passes_through_to_client(self):
        fixture = self._make_fixture(name='image1', is_public=True)
        image_id = self.service.create(self.context, fixture)['id']

        image_meta = self.service.show(self.context, image_id)
        expected = {
            'id': image_id,
            'name': 'image1',
            'is_public': True,
            'size': None,
            'min_disk': None,
            'min_ram': None,
            'disk_format': None,
            'container_format': None,
            'checksum': None,
            'created_at': self.NOW_DATETIME,
            'updated_at': self.NOW_DATETIME,
            'deleted_at': None,
            'deleted': None,
            'status': None,
            'properties': {},
            'owner': None,
        }
        self.assertEqual(image_meta, expected)

    def test_show_raises_when_no_authtoken_in_the_context(self):
        fixture = self._make_fixture(name='image1',
                                     is_public=False,
                                     properties={'one': 'two'})
        image_id = self.service.create(self.context, fixture)['id']
        self.context.auth_token = False
        self.assertRaises(exception.ImageNotFound,
                          self.service.show,
                          self.context,
                          image_id)

    def test_detail_passes_through_to_client(self):
        fixture = self._make_fixture(name='image10', is_public=True)
        image_id = self.service.create(self.context, fixture)['id']
        image_metas = self.service.detail(self.context)
        expected = [
            {
                'id': image_id,
                'name': 'image10',
                'is_public': True,
                'size': None,
                'min_disk': None,
                'min_ram': None,
                'disk_format': None,
                'container_format': None,
                'checksum': None,
                'created_at': self.NOW_DATETIME,
                'updated_at': self.NOW_DATETIME,
                'deleted_at': None,
                'deleted': None,
                'status': None,
                'properties': {},
                'owner': None,
            },
        ]
        self.assertEqual(image_metas, expected)

    def test_show_makes_datetimes(self):
        fixture = self._make_datetime_fixture()
        image_id = self.service.create(self.context, fixture)['id']
        image_meta = self.service.show(self.context, image_id)
        self.assertEqual(image_meta['created_at'], self.NOW_DATETIME)
        self.assertEqual(image_meta['updated_at'], self.NOW_DATETIME)

    def test_detail_makes_datetimes(self):
        fixture = self._make_datetime_fixture()
        self.service.create(self.context, fixture)
        image_meta = self.service.detail(self.context)[0]
        self.assertEqual(image_meta['created_at'], self.NOW_DATETIME)
        self.assertEqual(image_meta['updated_at'], self.NOW_DATETIME)

    def test_download_with_retries(self):
        tries = [0]

        class MyGlanceStubClient(glance_stubs.StubGlanceClient):
            """A client that fails the first time, then succeeds."""
            def get(self, image_id):
                if tries[0] == 0:
                    tries[0] = 1
                    raise glanceclient.exc.ServiceUnavailable('')
                else:
                    return {}

        client = MyGlanceStubClient()
        service = self._create_image_service(client)
        image_id = 1  # doesn't matter
        writer = NullWriter()

        # When retries are disabled, we should get an exception
        self.flags(glance_num_retries=0)
        self.assertRaises(exception.GlanceConnectionFailed,
                service.download, self.context, image_id, writer)

        # Now lets enable retries. No exception should happen now.
        tries = [0]
        self.flags(glance_num_retries=1)
        service.download(self.context, image_id, writer)

    def test_download_file_url(self):
        class MyGlanceStubClient(glance_stubs.StubGlanceClient):
            """A client that returns a file url."""

            (outfd, s_tmpfname) = tempfile.mkstemp(prefix='directURLsrc')
            outf = os.fdopen(outfd, 'w')
            inf = open('/dev/urandom', 'r')
            for i in range(10):
                _data = inf.read(1024)
                outf.write(_data)
            outf.close()

            def get(self, image_id):
                return type('GlanceTestDirectUrlMeta', (object,),
                            {'direct_url': 'file://%s' + self.s_tmpfname})

        client = MyGlanceStubClient()
        (outfd, tmpfname) = tempfile.mkstemp(prefix='directURLdst')
        writer = os.fdopen(outfd, 'w')

        service = self._create_image_service(client)
        image_id = 1  # doesn't matter

        self.flags(allowed_direct_url_schemes=['file'])
        service.download(self.context, image_id, writer)
        writer.close()

        # compare the two files
        rc = filecmp.cmp(tmpfname, client.s_tmpfname)
        self.assertTrue(rc, "The file %s and %s should be the same" %
                        (tmpfname, client.s_tmpfname))
        os.remove(client.s_tmpfname)
        os.remove(tmpfname)

    def test_client_forbidden_converts_to_imagenotauthed(self):
        class MyGlanceStubClient(glance_stubs.StubGlanceClient):
            """A client that raises a Forbidden exception."""
            def get(self, image_id):
                raise glanceclient.exc.Forbidden(image_id)

        client = MyGlanceStubClient()
        service = self._create_image_service(client)
        image_id = 1  # doesn't matter
        writer = NullWriter()
        self.assertRaises(exception.ImageNotAuthorized, service.download,
                          self.context, image_id, writer)

    def test_client_httpforbidden_converts_to_imagenotauthed(self):
        class MyGlanceStubClient(glance_stubs.StubGlanceClient):
            """A client that raises a HTTPForbidden exception."""
            def get(self, image_id):
                raise glanceclient.exc.HTTPForbidden(image_id)

        client = MyGlanceStubClient()
        service = self._create_image_service(client)
        image_id = 1  # doesn't matter
        writer = NullWriter()
        self.assertRaises(exception.ImageNotAuthorized, service.download,
                          self.context, image_id, writer)

    def test_client_notfound_converts_to_imagenotfound(self):
        class MyGlanceStubClient(glance_stubs.StubGlanceClient):
            """A client that raises a NotFound exception."""
            def get(self, image_id):
                raise glanceclient.exc.NotFound(image_id)

        client = MyGlanceStubClient()
        service = self._create_image_service(client)
        image_id = 1  # doesn't matter
        writer = NullWriter()
        self.assertRaises(exception.ImageNotFound, service.download,
                          self.context, image_id, writer)

    def test_client_httpnotfound_converts_to_imagenotfound(self):
        class MyGlanceStubClient(glance_stubs.StubGlanceClient):
            """A client that raises a HTTPNotFound exception."""
            def get(self, image_id):
                raise glanceclient.exc.HTTPNotFound(image_id)

        client = MyGlanceStubClient()
        service = self._create_image_service(client)
        image_id = 1  # doesn't matter
        writer = NullWriter()
        self.assertRaises(exception.ImageNotFound, service.download,
                          self.context, image_id, writer)

    def test_glance_client_image_id(self):
        fixture = self._make_fixture(name='test image')
        image_id = self.service.create(self.context, fixture)['id']
        (service, same_id) = glance.get_remote_image_service(
                self.context, image_id)
        self.assertEquals(same_id, image_id)

    def test_glance_client_image_ref(self):
        fixture = self._make_fixture(name='test image')
        image_id = self.service.create(self.context, fixture)['id']
        image_url = 'http://something-less-likely/%s' % image_id
        (service, same_id) = glance.get_remote_image_service(
                self.context, image_url)
        self.assertEquals(same_id, image_id)
        self.assertEquals(service._client.host,
                'something-less-likely')


def _create_failing_glance_client(info):
    class MyGlanceStubClient(glance_stubs.StubGlanceClient):
        """A client that fails the first time, then succeeds."""
        def get(self, image_id):
            info['num_calls'] += 1
            if info['num_calls'] == 1:
                raise glanceclient.exc.ServiceUnavailable('')
            return {}

    return MyGlanceStubClient()


class TestGlanceClientWrapper(utils.BaseTestCase):

    def setUp(self):
        super(TestGlanceClientWrapper, self).setUp()
        # host1 has no scheme, which is http by default
        self.flags(glance_api_servers=['host1:9292', 'https://host2:9293',
            'http://host3:9294'])

        # Make the test run fast
        def _fake_sleep(secs):
            pass
        self.stubs.Set(time, 'sleep', _fake_sleep)

    def test_static_client_without_retries(self):
        self.flags(glance_num_retries=0)

        ctxt = context.RequestContext('fake', 'fake')
        fake_host = 'host4'
        fake_port = 9295
        fake_use_ssl = False

        info = {'num_calls': 0}

        def _fake_create_glance_client(context, host, port, use_ssl, version):
            self.assertEqual(host, fake_host)
            self.assertEqual(port, fake_port)
            self.assertEqual(use_ssl, fake_use_ssl)
            return _create_failing_glance_client(info)

        self.stubs.Set(glance, '_create_glance_client',
                _fake_create_glance_client)

        client = glance.GlanceClientWrapper(context=ctxt,
                host=fake_host, port=fake_port, use_ssl=fake_use_ssl)
        self.assertRaises(exception.GlanceConnectionFailed,
                client.call, ctxt, 1, 'get', 'meow')
        self.assertEqual(info['num_calls'], 1)

    def test_default_client_without_retries(self):
        self.flags(glance_num_retries=0)

        ctxt = context.RequestContext('fake', 'fake')

        info = {'num_calls': 0,
                'host': 'host1',
                'port': 9292,
                'use_ssl': False}

        # Leave the list in a known-order
        def _fake_shuffle(servers):
            pass

        def _fake_create_glance_client(context, host, port, use_ssl, version):
            self.assertEqual(host, info['host'])
            self.assertEqual(port, info['port'])
            self.assertEqual(use_ssl, info['use_ssl'])
            return _create_failing_glance_client(info)

        self.stubs.Set(random, 'shuffle', _fake_shuffle)
        self.stubs.Set(glance, '_create_glance_client',
                _fake_create_glance_client)

        client = glance.GlanceClientWrapper()
        client2 = glance.GlanceClientWrapper()
        self.assertRaises(exception.GlanceConnectionFailed,
                client.call, ctxt, 1, 'get', 'meow')
        self.assertEqual(info['num_calls'], 1)

        info = {'num_calls': 0,
                'host': 'host2',
                'port': 9293,
                'use_ssl': True}

        def _fake_shuffle2(servers):
            # fake shuffle in a known manner
            servers.append(servers.pop(0))

        self.stubs.Set(random, 'shuffle', _fake_shuffle2)

        self.assertRaises(exception.GlanceConnectionFailed,
                client2.call, ctxt, 1, 'get', 'meow')
        self.assertEqual(info['num_calls'], 1)

    def test_static_client_with_retries(self):
        self.flags(glance_num_retries=1)

        ctxt = context.RequestContext('fake', 'fake')
        fake_host = 'host4'
        fake_port = 9295
        fake_use_ssl = False

        info = {'num_calls': 0}

        def _fake_create_glance_client(context, host, port, use_ssl, version):
            self.assertEqual(host, fake_host)
            self.assertEqual(port, fake_port)
            self.assertEqual(use_ssl, fake_use_ssl)
            return _create_failing_glance_client(info)

        self.stubs.Set(glance, '_create_glance_client',
                _fake_create_glance_client)

        client = glance.GlanceClientWrapper(context=ctxt,
                host=fake_host, port=fake_port, use_ssl=fake_use_ssl)
        client.call(ctxt, 1, 'get', 'meow')
        self.assertEqual(info['num_calls'], 2)

    def test_default_client_with_retries(self):
        self.flags(glance_num_retries=1)

        ctxt = context.RequestContext('fake', 'fake')

        info = {'num_calls': 0,
                'host0': 'host1',
                'port0': 9292,
                'use_ssl0': False,
                'host1': 'host2',
                'port1': 9293,
                'use_ssl1': True}

        # Leave the list in a known-order
        def _fake_shuffle(servers):
            pass

        def _fake_create_glance_client(context, host, port, use_ssl, version):
            attempt = info['num_calls']
            self.assertEqual(host, info['host%s' % attempt])
            self.assertEqual(port, info['port%s' % attempt])
            self.assertEqual(use_ssl, info['use_ssl%s' % attempt])
            return _create_failing_glance_client(info)

        self.stubs.Set(random, 'shuffle', _fake_shuffle)
        self.stubs.Set(glance, '_create_glance_client',
                _fake_create_glance_client)

        client = glance.GlanceClientWrapper()
        client2 = glance.GlanceClientWrapper()
        client.call(ctxt, 1, 'get', 'meow')
        self.assertEqual(info['num_calls'], 2)

        def _fake_shuffle2(servers):
            # fake shuffle in a known manner
            servers.append(servers.pop(0))

        self.stubs.Set(random, 'shuffle', _fake_shuffle2)

        info = {'num_calls': 0,
                'host0': 'host2',
                'port0': 9293,
                'use_ssl0': True,
                'host1': 'host3',
                'port1': 9294,
                'use_ssl1': False}

        client2.call(ctxt, 1, 'get', 'meow')
        self.assertEqual(info['num_calls'], 2)


class TestGlanceUrl(utils.BaseTestCase):

    def test_generate_glance_http_url(self):
        generated_url = glance.generate_glance_url()
        http_url = "http://%s:%d" % (CONF.glance_host, CONF.glance_port)
        self.assertEqual(generated_url, http_url)

    def test_generate_glance_https_url(self):
        self.flags(glance_protocol="https")
        generated_url = glance.generate_glance_url()
        https_url = "https://%s:%d" % (CONF.glance_host, CONF.glance_port)
        self.assertEqual(generated_url, https_url)
