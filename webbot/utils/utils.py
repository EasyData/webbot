#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from .dateparser import parse_date
from HTMLParser import HTMLParser
from chardet import detect
from datetime import datetime, timedelta
from lxml import etree, html
from lxml.html.clean import Cleaner
from random import randint
from scrapy import log
from scrapy.contrib.loader.processor import *
from scrapy.exceptions import CloseSpider
from scrapy.utils.markup import remove_tags
from scrapy.utils.url import canonicalize_url
from urllib import urlencode
from urllib2 import urlopen, urlparse
import base64
import codecs
import hashlib
import imp
import json
import jsonpath
import math
import os.path
import pprint
import re
import string
import tempfile
import time
import unicodedata
import zlib

try:
    from cPickle import pickle
except ImportError:
    import pickle

try:
    from termcolor import colored
except ImportError:
    def colored(text, color=None, on_color=None, attrs=None): return text

def R(x): return colored(x, 'red',    attrs=['bold'])
def G(x): return colored(x, 'green',  attrs=['dark', 'bold'])
def B(x): return colored(x, 'blue',   attrs=['bold'])
def Y(x): return colored(x, 'yellow', attrs=['dark', 'bold'])

def RR(x): return colored(x, 'white', 'on_red',    attrs=['bold'])
def GG(x): return colored(x, 'white', 'on_green',  attrs=['dark', 'bold'])
def BB(x): return colored(x, 'white', 'on_blue',   attrs=['bold'])
def YY(x): return colored(x, 'white', 'on_yellow', attrs=['dark', 'bold'])

def help():
    msg = 'If you want a thing done well, do it yourself!'
    msg = 'Simplicity is the ultimate sophistication!'
    log.msg(R(u''.join([unichr(0xfee0+ord(i)) if i.isalnum() else i for i in msg])))

def feed_uri_params_parser(params, spider):
    now = datetime.utcnow()
    params['date'] = now.strftime('%F')
    params['epoch'] = now.strftime('%s')
    params['random'] = randint(0, 32767)

def connect_uri(uri):

    uri = uri.replace('mongo://', 'mongodb://')

    if uri.startswith('mongodb://'):
        import pymongo
        parsed = pymongo.uri_parser.parse_uri(uri)
        database = parsed['database']
        collection = parsed['collection']
        host, port = parsed['nodelist'][0]

        cnn = pymongo.MongoClient(host=host, port=port)
        db = cnn[database]
        tbl = db[collection]

    elif uri.startswith('mysql://'):
        try:
            import mysql.connector as pymysql
        except ImportError:
            import pymysql
        parsed = urlparse.urlparse(uri)
        host = parsed.hostname
        port = parsed.port or 3306
        user = parsed.username
        passwd = parsed.password

        db, tbl = parsed.path.strip('/').split('.')
        cnn = pymysql.connect(
                                host=host,
                                port=port,
                                user=user,
                                passwd=passwd,
                                db=db,
                                charset='utf8'
                             )

    elif uri.startswith('redis://'):
        import redis
        cnn = None
        db = redis.StrictRedis.from_url(uri)
        tbl = None

    # TODO: encode type{PUSH/PULL/PUB/SUB} into qstr
    elif uri.startswith('tcp://'):
        import zmq
        cnn = zmq.Context()
        db = cnn.socket(zmq.PUSH)
        db.setsockopt(zmq.LINGER, 3000)
        db.connect(uri)
        tbl = None

    else:
        raise Exception('unknow uri <{}>'.format(uri))

    return (cnn, db, tbl)

def hash_url(url):
    url = canonicalize_url(url)
    sha1 = hashlib.sha1()
    sha1.update(url)
    return sha1.hexdigest()

def to_unicode(txt):
    if type(txt)==unicode:
        return txt
    elif type(txt)==str:
        enc = 'gbk' if detect(txt[:2048])['encoding'].lower()=='gb2312' else 'utf-8'
        return txt.decode(enc)
    else:
        return u''

def load_file(path):
    if os.path.exists(path):
        path = os.path.abspath(path)
        path = 'file://'+path
    try:
        if path.startswith('redis://') or path.startswith('mongodb://'):
            txt = '\n'.join(load_db(path))
        else:
            txt = urlopen(path, timeout=10).read()
        txt = to_unicode(txt)
    except Exception as ex:
        log.msg(u'cannot load file <{}>'.format(path.decode('utf-8')), level=log.ERROR)
        txt = u''
    return txt

def load_db(uri):
    uri, key = uri.rsplit('.', 1)
    gd = re.match(r'^(?P<key>\w+)(\[(?P<start>\d*):(?P<stop>\d*)\])?$', key).groupdict()
    key = gd['key']
    start = int(gd['start'] or 0)
    stop = int(gd['stop'] or -1)

    cnn,rdb,tbl = connect_uri(uri)

    if uri.startswith('redis://'):
        t = rdb.type(key)
        if t=='set':
            words = rdb.smembers(key)
        elif t=='zset':
            words = rdb.zrange(key, start, stop)
        elif t=='list':
            words = rdb.lrange(key, start, stop)
        elif t=='hash':
            words = rdb.hvals(key)
        elif t=='string':
            words = [rdb.get(key)]
        else:
            log.msg(u'invalid type <{}>({})'.format(key, t), level=log.WARNING)
            words = []
    elif uri.startswith('mongodb://'):
        span = stop-start+1
        span = span if span>0 else 0
        words = [u'{}'.format(i[key]) for i in tbl.find({}, {key:1}).skip(start).limit(span)]

    return set(words)

def load_cfg(path):
    cfg = json.loads(load_file(path))
    if 'base' in cfg:
        cfg = dict(load_cfg(cfg['base']).items()+cfg.items())
        del cfg['base']
    return cfg

def load_plugin(path):
    fd, fn = tempfile.mkstemp()
    os.write(fd, load_file(path).encode('utf-8'))
    mod = imp.load_source('plugin', fn)
    os.remove(fn)
    if os.path.exists(fn+'c'):
        os.remove(fn+'c')
    return mod

def generate_urls(obj, macro):
    try:
        if type(obj)==list:
            for url in obj:
                yield macro.expand(url)

        elif type(obj)==dict:
            base = macro.expand(obj['base'].encode('utf-8'))
            us = urlparse.urlsplit(base)
            qstr = dict(urlparse.parse_qsl(us.query))
            qstr.update(obj.get('qstr', {}))
            base = urlparse.urlunsplit(us._replace(query=''))

            for k,v in qstr.iteritems():
                if type(v)==dict and type(v['val'])==unicode:
                    v = v['val'].encode(v.get('enc', 'utf-8'), errors='ignore')
                qstr[k] = macro.expand(v)

            if 'keywords' in obj:
                kw_obj = obj['keywords']
                for kw in load_keywords(kw_obj):
                    key = kw_obj['name'].encode('utf-8')
                    val = kw.encode(kw_obj.get('enc', 'utf-8'), errors='ignore') if type(kw)==unicode else str(kw)
                    col = kw_obj.get('col', 0)
                    sep = kw_obj.get('sep')
                    if col>0:
                        val = val.split(sep)[col-1]
                    if kw_obj.get('query', True):
                        qstr.update({key:val})
                        url = base+'?'+urlencode(qstr)
                    else:
                        url = base.replace(key, val)+'?'+urlencode(qstr)
                    macro.update({'sep':sep})
                    macro.bind(url, kw)
                    yield url
            else:
                url = base+'?'+urlencode(qstr)
                yield url

    except Exception as ex:
        log.msg(u'cannot generate urls: {}'.format(ex), level=log.ERROR)
        raise CloseSpider()

def load_keywords(kw_obj, msg='keywords'):
    keywords = set()

    if type(kw_obj)==dict:

        incfile = kw_obj.get('file') or kw_obj.get('incfile')
        if incfile:
            for line in load_file(incfile).splitlines():
                kw = line.strip()
                if kw and not kw.startswith('#'):
                    keywords.add(kw)

        excfile = kw_obj.get('excfile')
        if excfile:
            exc = set()
            for line in load_file(excfile).splitlines():
                kw = line.strip()
                if kw and not kw.startswith('#'):
                    exc.add(kw)
            keywords -= exc

        rang = kw_obj.get('range')
        if rang:
            start = rang.get('start', 0)
            stop = rang.get('stop', 0)
            step = rang.get('step', 1)
            for kw in range(start, stop, step):
                keywords.add(str(kw))

        for kw in kw_obj.get('list', []):
            keywords.add(kw)

        sub = kw_obj.get('sub')
        if sub:
            frm = sub.get('from')
            to = sub.get('to')
            keywords = {re.sub(frm, to, kw) for kw in keywords}

        log.msg(u'load {} from <{}>({})'.format(msg, incfile, len(keywords)))

    return keywords

class UnicodePrinter(pprint.PrettyPrinter):

    def __init__(self, indent=1, width=80, depth=None, stream=None, verbose=0):
        pprint.PrettyPrinter.__init__(self, indent, width, depth, stream)
        self.verbose = verbose

    def width(self, string):
        return sum(1+(unicodedata.east_asian_width(c) in 'WF') for c in string)

    def truncate(self, string, width):
        i = 0
        s = u''
        if width<0:
            string = string[::-1]
        for c in string:
            s += c
            i += unicodedata.east_asian_width(c) in 'WF'
            i += 1
            if i>math.fabs(width):
                break
        if width<0:
            s = s[::-1]
        return s

    def squeeze(self, string, width=74):
        if self.width(string)>width:
            string = u'{} {} {}'.format(self.truncate(string, 60), B(u'……'), self.truncate(string, -14))
        return string

    def format(self, obj, context, maxlevels, level):
        if isinstance(obj, unicode):
            v = obj
            if self.verbose<3:
                v = self.squeeze(v)
            return ('"%s"'%v.encode('utf8'), True, False)
        return pprint.PrettyPrinter.format(self, obj, context, maxlevels, level)

class MacroExpander(object):

    def __init__(self, env):
        self.bindings = dict()
        self.macros = dict()
        self.macros.update(env)

    def bind(self, url, kw):

        self.bindings[url] = kw

    def query(self, url):

        return self.bindings.get(url, '')

    def update(self, env={}):
        now = datetime.now().replace(microsecond=0)
        utcnow = datetime.utcnow().replace(microsecond=0)
        self.macros.update({
                'UTCNOW':   utcnow.strftime('%Y-%m-%d %H:%M:%S'),
                'NOW':      now.strftime('%Y-%m-%d %H:%M:%S'),
                'TODAY':    now.strftime('%Y-%m-%d'),
                'ITODAY':   '{}-{}-{}'.format(now.year, now.month, now.day),

                'YEAR':     now.strftime('%Y'),
                'MONTH':    now.strftime('%m'),
                'DAY':      now.strftime('%d'),
                'HOUR':     now.strftime('%H'),
                'MINUTE':   now.strftime('%M'),
                'SECOND':   now.strftime('%S'),

                'IYEAR':    str(now.year),
                'IMONTH':   str(now.month),
                'IDAY':     str(now.day),
                'IHOUR':    str(now.hour),
                'IMINUTE':  str(now.minute),
                'ISECOND':  str(now.second),

                'UNOW':     str(int(time.time())),
                'UTODAY':   str(int(time.mktime(time.strptime(now.strftime('%Y-%m-%d'), '%Y-%m-%d')))),
                'UENDDAY':  str(int(time.mktime(time.strptime(now.strftime('%Y-%m-%d 23:59:59'), '%Y-%m-%d %H:%M:%S'))))
        })
        self.macros.update(env)

    def expand(self, value, env={}):
        if type(value)!=str and type(value)!=unicode:
            return value

        kw = self.macros.get('keyword', '')
        sep = self.macros.get('sep')
        for key,col in re.findall(r'\$\{(COL(\d+))\}', value):
            col = int(col)
            if col==0:
                v = kw
            else:
                v = kw.split(sep)[col-1]
            env[key] = v

        env = {k:v for k,v in env.iteritems() if k.isupper()}
        self.update()
        env.update(self.macros)
        tpl = string.Template(value)
        return tpl.safe_substitute(env)

def first_n_pages(pattern, pages):
    if not pages:
        return None

    start = pages.get('start', 1)
    stop = pages.get('stop', 5)
    group = pages.get('group', 1)
    enc = pages.get('enc')

    def _filter(url):
        m = re.search(pattern, url)
        if m and start<=int(m.group(group))<stop:
            if enc:
                return urlparse.unquote(url).decode('utf-8').encode(enc)
            else:
                return url
        return None

    return _filter

def filter_data(query, data):
    for k,v in query.iteritems():
        if k=='delta':
            now = datetime.utcnow()
            if not (type(data)==datetime and (now-data).total_seconds()<v):
                return False
        elif k=='match':
            if not (type(data) in [str, unicode] and re.match(v, data)):
                return False
        elif k=='min':
            if data<v:
                return False
        elif k=='max':
            if data>v:
                return False
        else:
            log.msg(u'invalid query <{}>'.format(query), level=log.WARNING)
            return False
    return True

def get_ipaddr(ifname):
    try:
        import socket, fcntl, struct
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15])
        )[20:24])
    except Exception as ex:
        return '0.0.0.0'

def register_xpath_namespaces():
    fns = {
            'date':'http://exslt.org/dates-and-times',
            'dyn':'http://exslt.org/dynamic',
            'exsl':'http://exslt.org/common',
            'func':'http://exslt.org/functions',
            'math':'http://exslt.org/math',
            'random':'http://exslt.org/random',
            're':'http://exslt.org/regular-expressions',
            'set':'http://exslt.org/sets',
            'str':'http://exslt.org/strings'
    }
    for k,v in fns.iteritems():
        etree.FunctionNamespace(v).prefix = k

register_xpath_namespaces()

