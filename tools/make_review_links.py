#!/usr/bin/env python
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

"""Build useful gerrit query links for the wiki page.
"""

from __future__ import print_function

import argparse

import yaml

BASE_URL = 'https://review.openstack.org/#'

#label:Code-Review-1
OPEN = 'status:open'
VERIFIED = 'label:Verified=1'
NO_MINUS = '-label:Code-Review-1+-label:Code-Review-2'
PLUS_2 = 'label:Code-Review=2'


LINKS = [
    ('Potential+Merges', [OPEN, VERIFIED, NO_MINUS, PLUS_2]),
    ('No+Objections', [OPEN, VERIFIED, NO_MINUS]),
    ('No+Reviews', [OPEN, VERIFIED, NO_MINUS,
                    '-CodeReview-2+-CodeReview%252B1+-CodeReview%252B2']),
]


def make_title(s, level):
    p = '=' * level
    return p + ' ' + s + ' ' + p


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--infile',
        default='../governance/reference/programs.yaml',
        help='programs.yaml file',
    )
    parser.add_argument(
        '--title-level',
        type=int,
        default=3,
        help='wiki title level',
    )
    args = parser.parse_args()

    programs = yaml.load(open(args.infile, 'r'))
    program = programs['Common Libraries']

    # Get the list of repos that do not match the ^.*oslo.* pattern
    repos = [
        pr['repo'] for pr in program['projects']
        if 'oslo' not in pr['repo']
    ]
    # use a regex for the ones we can, to reduce URL length
    repos.append('^.*oslo.*')

    print(make_title('Review Links', args.title_level))
    print()

    sections = [
        '%s=%s' % (
            title,
            (
                '+'.join(extra) +
                '+(' + '+OR+'.join('project:' + p for p in repos) + ')'
            )
        )
        for title, extra in LINKS
    ]
    url = BASE_URL + '/dashboard/?title=Oslo+Dashboard&' + '&'.join(sections)
    print('* [%(url)s Oslo Review Dashboard]' % {
        'url': url,
    })

    print('* Open Reviews by Project')
    for r in repos:
        url = BASE_URL + '/q/' + OPEN + '+' + 'project:' + r + ',n,z'
        print('** [%(url)s %(repo)s]' % {
            'url': url,
            'repo': r,
        })

if __name__ == '__main__':
    main()
