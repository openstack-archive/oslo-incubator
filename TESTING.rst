===========================
Testing Your OpenStack Code
===========================
------------
A Quickstart
------------

This is designed to be enough information for you to run your first tests.
Detailed information on testing can be found here: https://wiki.openstack.org/wiki/Testing

*Install pip*::

  [apt-get | yum] install python-pip
More information on pip here: http://www.pip-installer.org/en/latest/

*Use pip to install tox*::

  pip install tox

Run The Tests
-------------

*Navigate to the project's root directory and execute*::

  tox
Note: completing this command may take a long time (depends on system resources)
also, you might not see any output until tox is complete.

Information about tox can be found here: http://testrun.org/tox/latest/


Run The Tests in One Environment
--------------------------------

Tox will run your entire test suite in the environments specified in the project tox.ini::

  [tox]

  envlist = <list of available environments>

To run the test suite in just one of the environments in envlist execute::

  tox -e <env>
so for example, *run the test suite in py26*::

  tox -e py26

Run One Test
------------

To run individual tests with tox:

if testr is in tox.ini, for example::

  [testenv]

  includes "python setup.py testr --slowest --testr-args='{posargs}'"

run individual tests with the following syntax::

  tox -e <env> -- path.to.module:Class.test
so for example, *run the cpu_limited test in Nova*::

  tox -e py27 -- nova.tests.test_claims:ClaimTestCase.test_cpu_unlimited

if nose is in tox.ini, for example::

  [testenv]

  includes "nosetests {posargs}"

run individual tests with the following syntax::

  tox -e <env> -- --tests path.to.module:Class.test
so for example, *run the list test in Glance*::

  tox -e py27 -- --tests glance.tests.unit.test_auth.py:TestImageRepoProxy.test_list

Need More Info?
---------------

More information about testr: https://wiki.openstack.org/wiki/Testr

More information about nose: https://nose.readthedocs.org/en/latest/


More information about testing OpenStack code can be found here:
https://wiki.openstack.org/wiki/Testing
