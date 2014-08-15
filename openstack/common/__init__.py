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

from oslo.utils import importutils
import six

six.add_move(six.MovedModule('mox', 'mox', 'mox3.mox'))

# FIXME(dims): The mandate in oslo.utils spec is to switch all following
# calls to use stevedore. Let's just monkey patch for now.
importutils.import_class = importutils._import_class
importutils.import_object = importutils._import_object
importutils.import_object_ns = importutils._import_object_ns
importutils.import_module = importutils._import_module
