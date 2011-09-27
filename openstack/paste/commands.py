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

from paste.script import command
from paste.script import create_distro

class OpenstackCommand(create_distro.CreateDistroCommand):
    summary = 'Create the file layout for a Openstack project'
    description = """\
    Create a new Openstack project. The project will be layed out according
    to current Openstack preference.
    """

    # NOTE(jkoelker): Override the parser to wipe out the options
    parser = command.Command.standard_parser(simulate=True,
                                             no_interactive=True,
                                             quiet=True,
                                             overwrite=True)
    parser.add_option('-o', '--output-dir',
                      dest='output_dir',
                      metavar='DIR',
                      default='.',
                      help="Write put the directory into DIR (default current directory)")

    def command(self):
        # NOTE(jkoelker): Only support the *one* Openstack template
        self.options.templates = ['openstack']

        # NOTE(jkoelekr): We fake out what we don't want
        self.options.list_templates = False
        self.options.list_variables = False
        self.options.config = False
        self.options.inspect_files = False
        self.options.svn_repository = False
        create_distro.CreateDistroCommand.command(self)
