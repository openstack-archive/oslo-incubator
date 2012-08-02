#!/usr/bin/env python
import json
import os

from Crypto.PublicKey import DSA


key = DSA.generate(1024)
try:
    os.mkdir("/etc/openstack")
except OSError as e:
    if e.errno == 17:
        pass
    else:
        raise

os.umask(077)
fh = open("/etc/openstack/private_dsa_key", "w")
json.dump(key.keydata, fh)
fh.close()
