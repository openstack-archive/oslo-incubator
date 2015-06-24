#!/bin/bash
#
# Script to replace imports from the 'oslo' namespace package with the
# appropriate alternative in the dist-specific packages.
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

name=$(python setup.py --name)
dir=${1:-$name}

echo "Updating $dir"
sed -i \
    -e 's/from oslo\./from oslo_/g' \
    -e 's/import oslo\./import oslo_/g' \
    -e 's/from oslo import i18n/import oslo_i18n as i18n/g' \
    -e 's/from oslo import messaging/import oslo_messaging as messaging/g' \
    -e 's/from oslo import config/import oslo_config as config/g' \
    -e 's/from oslo import serialization/import oslo_serialization as serialization/g' \
    -e 's/from oslo import utils/import oslo_utils as utils/g' \
    -e 's/oslo\.i18n\.TranslatorFactory/oslo_i18n.TranslatorFactory/g' \
    $(find $dir -name '*.py' | grep -v "$name/tests/unit/test_hacking.py")

set -x

git grep 'from oslo import'
git grep 'oslo\.'
