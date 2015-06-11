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

"""
New core email content generator.
"""

import argparse

import jinja2
import parawrap


CORE_TPL = """
Greetings all stackers,

I propose that we add {{FULL_NAME}} to the {{TEAM_CORE}} team.

{{FIRST_NAME}} has been actively contributing to {{TEAM}} for a while now, both
in helping make {{TEAM}} better via code contribution(s) and by helping with
the review load when {{HE_SHE_LOWER}} can. {{HE_SHE}} has provided quality
reviews and is doing an awesome job with the various {{TEAM}} concepts and
helping make {{TEAM}} the best it can be!

Overall I think {{HE_SHE_LOWER}} would make a great addition to the core
review team.

Please respond with +1/-1.

Thanks much!

--

{{ME}}
"""
CORE_TPL = CORE_TPL.strip()


def expand_template(contents, params):
    if not params:
        params = {}
    tpl = jinja2.Template(source=contents, undefined=jinja2.StrictUndefined)
    return tpl.render(**params)


def generate_email(args):
    params = {
        'FULL_NAME': args.who,
        'HE_SHE': args.gender.title(),
        'LINKS': [],
        'TEAM_CORE': '%s-core' % args.team,
        'ME': args.sender,
        'PROJECT_USING': 'FILL_ME_IN',
    }
    params['HE_SHE_LOWER'] = params['HE_SHE'].lower()
    params['TEAM'] = params['TEAM_CORE'].split("-")[0].strip().lower()
    params['FIRST_NAME'] = params['FULL_NAME'].split()[0]
    contents = expand_template(CORE_TPL, params)
    return parawrap.fill(contents.strip(), width=75)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adding-who', action="store", dest="who",
                        required=True, metavar="<full-name>")
    parser.add_argument('--from-who', action="store", dest="sender",
                        metavar="<full-name>", required=True)
    parser.add_argument('--team', action="store", dest="team",
                        metavar="<team>", required=True)
    parser.add_argument('--gender', action="store", dest="gender",
                        metavar="<he/she>", required=True)
    args = parser.parse_args()
    print(generate_email(args))


if __name__ == '__main__':
    main()
