#! /usr/bin/python3

import bcrypt

salt = bcrypt.gensalt(rounds=8, prefix=b'2a')
print(salt)
