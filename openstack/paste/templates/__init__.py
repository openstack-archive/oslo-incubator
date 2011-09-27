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

from paste.script import templates as paste_templates
from paste.util import template


class OpenstackTemplate(paste_templates.Template):
    """Create a new Openstack Project based on the recomended skeleton."""
    _template_dir = 'openstack'
    summary = 'Template for an Openstack project'
    vars = [paste_templates.var('description',
                                'One-line description of the package'),
           ]
    template_renderer = staticmethod(template.paste_script_template_renderer)
