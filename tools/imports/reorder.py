# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 SINA Corporation
# All Rights Reserved.
# Author: Zhongyue Luo <lzyeval@gmail.com>
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

"""Reorders imports by full module path."""

import os
import shutil
import sys


PY_EXT = '.py'
IMPORT_KEYWORDS = ['from', 'import']
DELIMITER = '$'


def reorder_imports(filepath):
    tmp_filepath = '%s.tmp' % filepath
    blank_line_cnt = 0
    bypass = False
    is_import = False
    unsorted_imports = list()
    orig_file = open(filepath, 'r')
    temp_file = open(tmp_filepath, 'w')
    for raw_line in orig_file:
        striped_line = raw_line.strip()
        # NOTE(lzyeval): analyze line
        if bypass:
            pass
        elif not striped_line:
            is_import = False
            blank_line_cnt += 1
            if blank_line_cnt == 2:
                bypass = True
        elif not is_import and is_import_str(raw_line):
            is_import = True
            blank_line_cnt = 0
        else:
            blank_line_cnt = 0
        # NOTE(lzyeval): process line
        if is_import:
            if is_import_str(raw_line):
                unsorted_imports.append(striped_line)
            else:
                last_import = unsorted_imports.pop()
                unsorted_imports.append(' '.join([last_import, striped_line]))
        else:
            if unsorted_imports:
                sorted_imports = sort(unsorted_imports)
                for import_str in sorted_imports:
                    temp_file.write(import_str)
                    temp_file.write('\n')
                del unsorted_imports[:]
            temp_file.write(raw_line)
    # NOTE(lzyeval): flush remaining imports
    if unsorted_imports:
        sorted_imports = sort(unsorted_imports)
        for import_str in sorted_imports:
            temp_file.write(import_str)
            temp_file.write('\n')
    orig_file.close()
    temp_file.close()
    shutil.move(tmp_filepath, filepath)


def is_import_str(input_str):
    result = False
    for keyword in IMPORT_KEYWORDS:
        if input_str.startswith(keyword):
            result = True
            break
    return result


def sort(imports):
    tagged_imports = list()
    for import_str in imports:
        import_str_tokens = map(lambda x: x.lower(),
                                filter(lambda x: x not in IMPORT_KEYWORDS,
                                       import_str.split()))
        tagged_imports.append("%s%s%s" % (".".join(import_str_tokens),
                                          DELIMITER,
                                          import_str))
    tagged_imports.sort()
    return map(lambda x: x.split(DELIMITER)[1], tagged_imports)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "usage: python %s <package_dir>" % sys.argv[0]
        sys.exit(0)
    path = sys.argv[1]
    for (dirpath, dirname, filenames) in os.walk(path):
        for filename in filter(lambda x: x.endswith(PY_EXT), filenames):
            reorder_imports(os.path.join(dirpath, filename))
