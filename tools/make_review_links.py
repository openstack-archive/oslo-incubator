#!/usr/bin/env python
"""Build useful gerrit query links for the wiki page.
"""

import argparse

import yaml

BASE_URL = 'https://review.openstack.org/#/q/'

#label:Code-Review-1
OPEN = 'status:open'
VERIFIED = 'label:Verified=1'
NO_MINUS = '-label:Code-Review-1+-label:Code-Review-2'
PLUS_2 = 'label:Code-Review=2'


LINKS = [
    ('Potential Merges', [OPEN, VERIFIED, NO_MINUS, PLUS_2]),
    ('No Objections', [OPEN, VERIFIED, NO_MINUS]),
    ('No Reviews', [OPEN, VERIFIED, NO_MINUS,
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
    parser.add_argument(
        '--program',
        default='Common Libraries',
        help='program to work on',
    )
    args = parser.parse_args()

    programs = yaml.load(open(args.infile, 'r'))
    program = programs[args.program]

    repos = [pr['repo'] for pr in program['projects']]

    print make_title('Links', args.title_level)
    print

    print '* Cross-Repository Queries'
    for title, extra in LINKS:
        url = (
            BASE_URL +
            '+'.join(extra) +
            '+(' + '+OR+'.join('project:' + p for p in repos) + '),n,z'
        )
        print '** [%(url)s %(title)s]' % {
            'url': url,
            'title': title,
        }

    print '* Open Reviews by Project'
    for r in repos:
        url = BASE_URL + '+' + OPEN + '+' + 'project:' + r
        print '** [%(url)s %(repo)s]' % {
            'url': url,
            'repo': r,
        }

if __name__ == '__main__':
    main()