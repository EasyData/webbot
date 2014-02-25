#!/usr/bin/env python
# THIS FILE IS COPYED FROM <broker.api>

import zlib
import zmq

try:
    import cPickle as pickle
except ImportError:
    import pickle


class MessageSender(object):
    r"""push obj to zmq socket"""

    def __init__(self, uri):
        r"""create a zmq socket from a uri"""
        self.ctx = zmq.Context()
        self.skt = self.ctx.socket(zmq.PUSH)
        self.skt.setsockopt(zmq.LINGER, 3000)
        self.skt.connect(uri)

    def send(self, obj):
        r"""send zipped obj to zmq socket"""
        buf = Zipper.dumps(obj)
        self.skt.send(buf, flags=zmq.NOBLOCK)

    def term(self):
        r"""close zmq socket"""
        self.skt.close()
        self.ctx.term()


class Zipper(object):
    r"""obj serialization util"""

    @staticmethod
    def dumps(obj):
        r"""serialize obj"""
        buf = pickle.dumps(obj, -1)
        return zlib.compress(buf)

    @staticmethod
    def loads(buf):
        r"""unserialize obj"""
        buf = zlib.decompress(buf)
        return pickle.loads(buf)

