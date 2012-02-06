from setuptools import setup, find_packages
from openstack.common.setup import parse_requirements
from openstack.common.setup import parse_dependency_links
from openstack.common.setup import write_requirements


version = '0.1'

requires = parse_requirements()
depend_links = parse_dependency_links()
write_requirements()

setup(name='openstack.common',
      version=version,
      description="Common components for Openstack",
      long_description="""\
Common components for Openstack including paster templates.
""",
      classifiers=[
          'Development Status :: 4 - Beta',
          'License :: OSI Approved :: Apache Software License',
          'Operating System :: POSIX :: Linux',
          'Programming Language :: Python :: 2.6',
          'Environment :: No Input/Output (Daemon)',
          ],
      keywords='openstack',
      author='OpenStack',
      author_email='openstack@lists.launchpad.net',
      url='http://www.openstack.org/',
      license='Apache Software License',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=True,
      install_requires=requires,
      dependency_links=depend_links,
      entry_points="""
      # -*- Entry points: -*-
      """,
      namespace_packages=['openstack'],
      )
