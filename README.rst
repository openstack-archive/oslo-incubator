------------------
The Oslo Incubator
------------------

The Oslo program produces a set of python libraries containing
infrastructure code shared by OpenStack projects. The APIs provided by
these libraries should be high quality, stable, consistent and
generally useful.

The process of developing a new Oslo API usually begins by taking code
which is common to some OpenStack projects and moving it into this
repository. Incubation shouldn't be seen as a long term option for any
API - it is merely a stepping stone to inclusion into a published Oslo
library.

For more information, see our wiki page:

   https://wiki.openstack.org/wiki/Oslo

Running Tests
-------------

To run tests in virtualenvs (preferred):

  sudo pip install tox
  tox

To run tests in the current environment:

  sudo pip install -r requirements.txt
  nosetests

To use ability to run all tests under backend which is not sqlite, you should
define environment variable OS_TEST_DBAPI_ADMIN_CONNECTION. Environment
variable contain user defined database uri in the format:
driver://username:password@host/database. Required to create a temporary test
database.
