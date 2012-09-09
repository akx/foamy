from foamy.objs import Request
from lxml import etree
import hashlib
import os
import tempfile
import time
try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO


class ResourceCache(object):
    def __init__(self, expiry_seconds=86400):
        self.cache_path = os.path.join(tempfile.gettempdir(), "foamy-resources")
        if not os.path.isdir(self.cache_path):
            os.makedirs(self.cache_path)
        self.expiry_seconds = expiry_seconds

    def key_to_path(self, key):
        return os.path.join(self.cache_path, hashlib.md5(unicode(key).encode("UTF-8")).hexdigest())

    def get_fp(self, key):
        path = self.key_to_path(key)
        if not os.path.isfile(path) or (time.time() - os.stat(path).st_mtime) > self.expiry_seconds:
            return None
        return file(path, "rb")

    def get(self, key):
        fp = self.get_fp(key)
        if fp:
            with fp:
                return fp.read()
        else:
            return None

    def put(self, key, data):
        with file(self.key_to_path(key), "wb") as out_fp:
            out_fp.write(data)


class ResourceLoader(object):
    def __init__(self, transport, cache=None):
        self.transport = transport
        self.cache = cache or ResourceCache()

    def _download(self, url):
        if "://" in url:  # XXX: Worst heuristic ever
            data = self.transport.dispatch(Request(url)).data
        else:
            with file(url, "rb") as fp:
                return fp.read()

    def load_xml(self, url):
        fp = self.cache.get_fp(url)
        if fp:
            with fp:
                return etree.parse(fp)
        else:
            data = self._download(url)
            self.cache.put(url, data)
            return etree.parse(StringIO(data))

    def get(self, url):
        data = self.cache.get(url)
        if not data:
            data = self._download(url)
            self.cache.put(url, data)
        return data
