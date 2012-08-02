#!/usr/bin/env python
from Crypto.PublicKey import DSA
import json

key = DSA.generate(2048)
fh = open("/etc/nova/private_dsa_key", "w")
json.dump(fh, key.keydata)
