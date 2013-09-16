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

To run tests using MySQL or PostgreSQL as a DB backend do:

  OS_TEST_DBAPI_ADMIN_CONNECTION=mysql://user:password@host/database tox -e py27

Note, that your DB user must have permissions to create and drop databases.
