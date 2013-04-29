from openstack.common.apiclient import base
from openstack.common.apiclient import client
from openstack.common.apiclient import exceptions

from tests.unit.apiclient import fakes
from tests import utils


class Flavor(base.Resource):
    pass


class FlavorManager(base.ManagerWithFind):
    resource_class = Flavor

    def list(self, detailed=True, is_public=True):
        detail = ""
        if detailed:
            detail = "/detail"

        return self._list("/flavors%s" % (detail), "flavors")

    def get(self, flavor):
        return self._get("/flavors/%s" % base.getid(flavor), "flavor")


class FakeHttpClient(fakes.FakeHttpClient):
    #
    # Flavors
    #

    def get_flavors(self, **kw):
        return (200, {}, {'flavors': [
            {'id': 1, 'name': '256 MB Server'},
            {'id': 2, 'name': '512 MB Server'},
            {'id': 'aa1', 'name': '128 MB Server'}
        ]})

    def get_flavors_detail(self, **kw):
        return (200, {}, {'flavors': [
            {'id': 1, 'name': '256 MB Server', 'ram': 256, 'disk': 10,
             'OS-FLV-EXT-DATA:ephemeral': 10,
             'os-flavor-access:is_public': True,
             'links': {}},
            {'id': 2, 'name': '512 MB Server', 'ram': 512, 'disk': 20,
             'OS-FLV-EXT-DATA:ephemeral': 20,
             'os-flavor-access:is_public': False,
             'links': {}},
            {'id': 'aa1', 'name': '128 MB Server', 'ram': 128, 'disk': 0,
             'OS-FLV-EXT-DATA:ephemeral': 0,
             'os-flavor-access:is_public': True,
             'links': {}}
        ]})

    def get_flavors_1(self, **kw):
        return (
            200,
            {},
            {'flavor': self.get_flavors_detail()[2]['flavors'][0]}
        )


class ComputeClient(client.BaseClient):

    service_type = "compute"

    def __init__(self, http_client, extensions=None):
        super(ComputeClient, self).__init__(
            http_client, extensions=extensions)

        self.flavors = FlavorManager(self)


cs = ComputeClient(FakeHttpClient())


class BaseTest(utils.BaseTestCase):

    def test_resource_repr(self):
        r = base.Resource(None, dict(foo="bar", baz="spam"))
        self.assertEqual(repr(r), "<Resource baz=spam, foo=bar>")

    def test_getid(self):
        self.assertEqual(base.getid(4), 4)

        class TmpObject(object):
            id = 4
        self.assertEqual(base.getid(TmpObject), 4)

    def test_resource_lazy_getattr(self):
        f = Flavor(cs.flavors, {'id': 1})
        self.assertEqual(f.name, '256 MB Server')
        cs.http_client.assert_called('GET', '/flavors/1')

        # Missing stuff still fails after a second get
        self.assertRaises(AttributeError, getattr, f, 'blahblah')

    def test_eq(self):
        # Two resources of the same type with the same id: equal
        r1 = base.Resource(None, {'id': 1, 'name': 'hi'})
        r2 = base.Resource(None, {'id': 1, 'name': 'hello'})
        self.assertEqual(r1, r2)

        # Two resoruces of different types: never equal
        r1 = base.Resource(None, {'id': 1})
        r2 = Flavor(None, {'id': 1})
        self.assertNotEqual(r1, r2)

        # Two resources with no ID: equal if their info is equal
        r1 = base.Resource(None, {'name': 'joe', 'age': 12})
        r2 = base.Resource(None, {'name': 'joe', 'age': 12})
        self.assertEqual(r1, r2)

    def test_findall_invalid_attribute(self):
        # Make sure findall with an invalid attribute doesn't cause errors.
        # The following should not raise an exception.
        cs.flavors.findall(vegetable='carrot')

        # However, find() should raise an error
        self.assertRaises(exceptions.NotFound,
                          cs.flavors.find,
                          vegetable='carrot')
