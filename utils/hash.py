# -*- encoding: utf-8 -*-

from __future__ import unicode_literals

import codecs
import hashlib
from django.utils.crypto import pbkdf2
from django.utils.six import string_types


def _TypeError(name, expected, val):
    return TypeError("'{0}' must be {1}, not {2}".format(
        name, expected, val.__class__.__name__))


class Hash(object):

    func = None
    salt = b"Eech7co8Ohloopo9Ol6baimi"

    def __init__(self, salt=None, func="sha1"):

        if func is not None:
            hashlib.new(func)  # may not be available
            self.func = func

        if salt is not None:
            if not isinstance(salt, bytes):
                raise _TypeError("salt", "bytes", salt)
            self.salt = salt

    def hash(self, val):
        """Calculate hash from value (must be bytes)."""

        if not isinstance(val, bytes):
            raise _TypeError("val", "bytes", val)

        rv = self.compute(val)

        if not isinstance(val, bytes):
            raise _TypeError("val", "bytes", rv)

        return rv

    def uhash(self, val):
        """Calculate hash from unicode value and return hex value as unicode"""

        if not isinstance(val, string_types):
            raise _TypeError("val", "str", val)

        return codecs.encode(self.hash(val.encode("utf-8")), "hex_codec").decode("utf-8")

    def compute(self, val):
        if self.func is None:
            return val

        h = hashlib.new(self.func)
        h.update(val)

        return h.digest()


class PBKDF2(Hash):
    
    def __init__(self, salt=None, iterations=1000, dklen=6, func=None):
        super(PBKDF2, self).__init__(salt)

        self.iterations = iterations
        self.dklen = dklen
        self.func = func

    def compute(self, val):
        return pbkdf2(val, self.salt, self.iterations, self.dklen, self.func)


def new():
    """Factory to create hash functions from configuration section. If an
    algorithm takes custom parameters, you can separate them by a colon like
    this: pbkdf2:arg1:arg2:arg3."""

    algorithm = 'pbkdf2'
    salt = 'Eech7co8Ohloopo9Ol6baimi'.encode('utf-8')

    if algorithm == "none":
        return Hash(salt, None)
    elif algorithm.startswith("pbkdf2"):
        kwargs = {}
        tail = algorithm.partition(":")[2]
        for func, key in ((int, "iterations"), (int, "dklen"), (str, "func")):
            head, _, tail = tail.partition(":")
            if not head:
                break
            kwargs[key] = func(head)

        return PBKDF2(salt, **kwargs)
    else:
        return Hash(salt, algorithm)

pbkdf2_hash = new().uhash

sha1 = Hash(func="sha1").uhash