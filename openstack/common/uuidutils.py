# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012 Intel Corporation.
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

"""
UUID related utilities and helper functions.
"""

import uuid


def uuid4():
    """Generate a random UUID."""
    return uuid.uuid4()


def uuid4_hex():
    """Generate a random UUID as a 32-character hexadecimal string."""
    return uuid.uuid4().hex


def uuid4_str():
    """Generate a random UUID as a 36-character canonical form string."""
    return str(uuid.uuid4())


def uuid4_randint():
    """Generate a random UUID as a 128-bit integer."""
    return int(uuid.uuid4())


def uuid5(namespace, name):
    """Generate a UUID from the SHA-1 hash of a namespace UUID and a name."""
    return uuid.uuid5(namespace, name)


def is_uuid_like(val):
    """For our purposes, a UUID is a canonical form string:

       aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
    """
    try:
        uuid.UUID(val)
        return True
    except (TypeError, ValueError, AttributeError):
        return False
