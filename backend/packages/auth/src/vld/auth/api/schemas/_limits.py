"""Length caps on everything that arrives in auth requests as a string."""

from __future__ import annotations

# 254 for an address is the limit of RFC 5321 §4.5.3.1.
MAX_EMAIL = 254

# A cap for memory; the byte limit of bcrypt is checked by the password policy.
MAX_PASSWORD = 128

# Our JWT is hundreds of bytes; room to grow.
MAX_JWT = 4096

# A token from a letter is `token_urlsafe(32)`, that is 43 characters.
MAX_EMAIL_TOKEN = 512

MAX_NAME = 100
MAX_GROUP_NUMBER = 32
MAX_INSTITUTION_NAME = 300
