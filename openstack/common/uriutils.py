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
userinfo = '([a-zA-Z0-9-_:]+@)?'
dec_octet = '([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])'
ipv4address = '%(dec_octet)s.%(dec_octet)s.%(dec_octet)s.%(dec_octet)s' % {
    'dec_octet': dec_octet
}
h16 = '[0-9a-fA-F]{,4}'
ls32 = '(%(h16)s:%(h16)s|%(ipv4address)s)' % {
    'h16': h16, 'ipv4address': ipv4address
}
ipv6address = ('((%(h16)s:){6}%(ls32)s|'
               '::(%(h16)s:){5}%(ls32)s|'
               '((%(h16)s))?::(%(h16)s:){4}%(ls32)s|'
               '((%(h16)s:){1}%(h16)s)?::(%(h16)s:){3}%(ls32)s|'
               '((%(h16)s:){,2}%(h16)s)?::(%(h16)s:){2}%(ls32)s|'
               '((%(h16)s:){,3}%(h16)s)?::(%(h16)s:){1}%(ls32)s|'
               '((%(h16)s:){,4}%(h16)s)?::%(ls32)s|'
               '((%(h16)s:){,5}%(h16)s)?::%(h16)s|'
               '((%(h16)s:){,6}%(h16)s)?::)') % {
                   'h16': h16,
                   'ls32': ls32
               }
unreserved = '[a-zA-Z0-9-._~]'
sub_delims = '[!$&\'()*+,;=]'
pct_encoded = '%[0-9a-fA-F][0-9a-fA-F]'
ipv_future = 'v[0-9a-fA-F]\.(%(unreserved)s|%(sub_delims)s|:)+' % {
    'unreserved': unreserved, 'sub_delims': sub_delims
}
ip_literal = '\[(%(ipv6address)s|%(ipv_future)s)\]' % {
    'ipv6address': ipv6address, 'ipv_future': ipv_future
}
reg_name = '(%(unreserved)s|%(pct_encoded)s|%(sub_delims)s)+' % {
    'unreserved': unreserved,
    'pct_encoded': pct_encoded,
    'sub_delims': sub_delims
}
host = '(%(ip_literal)s|%(ipv4address)s|%(reg_name)s)' % {
    'ip_literal': ip_literal, 'ipv4address': ipv4address, 'reg_name': reg_name
}
port = ('(:([1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|'
        '655[0-2][0-9]|6553[0-5]|[1-9][0-9]{3}))?')
authority = '%(userinfo)s%(host)s%(port)s' % {
    'userinfo': userinfo, 'host': host, 'port': port
}

# NOTE: The syntax components of path:
# path = path-abempty  ; begins with "/" or is empty
#      / path-absolute ; begins with "/" but not "//"
#      / path-noscheme ; begins with a non-colon segment
#      / path-rootless ; begins with a segment
#      / path-empty    ; zero characters
pchar = '(%(unreserved)s|%(pct_encoded)s|%(sub_delims)s|:|@)' % {
    'unreserved': unreserved,
    'pct_encoded': pct_encoded,
    'sub_delims': sub_delims
}
segment = '%s*' % pchar
segment_nz = '%s+' % pchar
segment_nz_nc = '(%(unreserved)s|%(pct_encoded)s|%(sub_delims)s|@)+' % {
    'unreserved': unreserved,
    'pct_encoded': pct_encoded,
    'sub_delims': sub_delims
}

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
path_empty = ''

hier_part = ('(//%(authority)s%(path_abempty)s|%(path_absolute)s|'
             '%(path_rootless)s|%(path_empty)s)') % {
                 'authority': authority,
                 'path_abempty': path_abempty,
                 'path_absolute': path_absolute,
                 'path_rootless': path_rootless,
                 'path_empty': path_empty
             }

query = '(\?[a-zA-Z0-9-._~%!$&\'()*+,;=:@/?]*)*'
fragment = '(#[a-zA-Z0-9-._~%!$&\'()*+,;=:@/?]*)*'

# The syntax components of URI are:
#   URI = scheme ":" hier-part [ "?" query ] [ "#" fragment ]
uri_pattern = '%(scheme)s:%(hier_part)s%(query)s%(fragment)s' % {
    'scheme': scheme, 'hier_part': hier_part,
    'query': query, 'fragment': fragment
}
reg_uri = re.compile(r'^(%s)$' % uri_pattern)


def is_valid_uri(val):
    """Returns validation of a value as a URI.

    The validation is based on RFC3986.

    """
    return reg_uri.search(val)
