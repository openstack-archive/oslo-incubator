# Copyright 2014 NEC Corporation. All rights reserved.
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
URI related utilities and helper functions.
"""

import re

# NOTE: The syntax of schema:
#  scheme = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )
scheme = '[a-zA-Z][a-zA-Z0-9+-.]+'

# NOTE: The syntax components of authority:
#  authority = [ userinfo "@" ] host [ ":" port ]
#    userinfo = *( unreserved / pct-encoded / sub-delims / ":" )
#    host     = IP-literal / IPv4address / reg-name
#    port     = *DIGIT
userinfo = '([a-zA-Z0-9-_:]+@){0,1}'
host = '[a-zA-Z0-9-_.:]+'
port = '(:[0-9]+){0,1}'
authority = '%(userinfo)s%(host)s%(port)s' % {
    'userinfo': userinfo, 'host': host, 'port': port
}

# NOTE: The syntax components of path:
# path = path-abempty  ; begins with "/" or is empty
#      / path-absolute ; begins with "/" but not "//"
#      / path-noscheme ; begins with a non-colon segment
#      / path-rootless ; begins with a segment
#      / path-empty    ; zero characters
pchar = '[a-zA-Z0-9-._~%!$&\'()*+,;=:@]'
segment = '%s*' % pchar
segment_nz = '%s+' % pchar
segment_nz_nc = '[a-zA-Z0-9-._~%!$&\'()*+,;=@]+'

path_abempty = '(/%s)*' % segment
path_absolute = '/(%(segment_nz)s)(/%(segment)s)*' % {
    'segment_nz': segment_nz, 'segment': segment
}
path_noscheme = '%(segment_nz_nc)s(/%(segment)s)*' % {
    'segment_nz_nc': segment_nz_nc, 'segment': segment
}
path_rootless = '%(segment_nz)s(/%(segment)s)*' % {
    'segment_nz': segment_nz, 'segment': segment
}
path = ('%(path_abempty)s|%(path_absolute)s|'
        '%(path_noscheme)s|%(path_rootless)s') % {
            'path_abempty': path_abempty,
            'path_absolute': path_absolute,
            'path_noscheme': path_noscheme,
            'path_rootless': path_rootless
        }
hier_part = '(%(authority)s%(path)s)' % {
    'authority': authority, 'path': path
}

query = '(\?[a-zA-Z0-9-._~%!$&\'()*+,;=:@/?]*)*'
fragment = '(#[a-zA-Z0-9-._~%!$&\'()*+,;=:@/?]*)*'

# The syntax components of URI are:
#   URI = scheme ":" hier-part [ "?" query ] [ "#" fragment ]
uri_pattern = '%(scheme)s://%(hier_part)s%(query)s%(fragment)s' % {
    'scheme': scheme, 'hier_part': hier_part,
    'query': query, 'fragment': fragment
}
reg_uri = re.compile(r'^(%s)$' % uri_pattern)


def is_uri_like(val):
    """Returns validation of a value as a URI.

    The validation is based on RFC3986.

    """
    return reg_uri.search(val)
