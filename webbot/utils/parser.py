#!/usr/bin/env python
# -*- coding: utf-8 -*-

from HTMLParser import HTMLParser
from functools import partial
from jsonpath import jsonpath
from lxml import html
from lxml.html.clean import Cleaner
from scrapy import log
from scrapy.contrib.loader.processor import *
from scrapy.utils.markup import remove_tags
import base64
import inspect
import re
import requests
import sys

try:
    from webbot.utils.dateparser import parse_date
except:
    pass

try:
    import simplejson as json
except ImportError:
    import json

class BaseParser(object):

    def __init__(self, inf):

        assert self.__class__.__name__.endswith('Parser')
        self.inf = inf

    def parse(self, data):

        return data
    
    def __call__(self, data):

        return MapCompose(self.parse)(data)

class HeadParser(BaseParser):

    def __call__(self, data):

        return data[:1]

class TailParser(BaseParser):

    def __call__(self, data):

        return data[1:]

class LastParser(BaseParser):

    def __call__(self, data):

        return data[-1:]

class LenParser(BaseParser):

    def __call__(self, data):

        return len(data)

class JoinParser(BaseParser):

    def __call__(self, data):

        data = BaseParser.__call__(self, data)
        sep = self.inf.get('sep', u' ')
        return [Join(sep)(data)]

class ListParser(BaseParser):

    def parse(self, data):

        return remove_tags(data).strip()

    def __call__(self, data):

        data = BaseParser.__call__(self, data)
        sep = self.inf.get('sep', u' ')
        return [Join(sep)(data)]

class HttpParser(BaseParser):

    def parse(self, data):

        url = data
        m = inf.get('method', 'get').upper()
        d = inf.get('data', {})
        e = inf.get('enc', 'utf-8')
        if m=='GET':
            return requests.get(url).content.decode(e)
        elif m=='POST':
            return requests.get(url, data=d).content.decode(e)
        else:
            return data

class MapParser(BaseParser):

    def parse(self, data):

        m = inf.get('map')
        d = inf.get('default')
        return m.get(data, d)

class XpathParser(BaseParser):

    def parse(self, data):

        qs = inf.get('query')
        dom = html.fromstring(data)
        return dom.xpath(qs)

class JpathParser(BaseParser):

    def parse(self, data):

        qs = inf.get('query')
        return jsonpath(json.loads(data), qs)

class FloatParser(BaseParser):

    def parse(self, data):

        try:
            data = data.replace(',', '')
            data = re.search(r'[.0-9]+', data).group(0)
            return float(data)
        except:
            return 0.0

class IntParser(BaseParser):

    def parse(self, data):

        try:
            data = data.replace(',', '')
            data = re.search(r'[.0-9]+', data).group(0)
            return int(data)
        except:
            return 0

class UnescParser(BaseParser):

    def parse(self, data):

        return HTMLParser().unescape(data)

class DateParser(BaseParser):

    def parse(self, data):

        fmt = self.inf.get('fmt', 'auto')
        tz = self.inf.get('tz', '+00:00')
        return parse_date(data, fmt, tz)

class CstParser(BaseParser):

    def parse(self, data):

        fmt = self.inf.get('fmt', 'auto')
        tz = '+08:00'
        return parse_date(data, fmt, tz)

class Base64Parser(BaseParser):

    def parse(self, data):
        return base64.decodestring(data)

class CleanParser(BaseParser):

    def parse(self, data):
        try:
            cleaner = Cleaner(style=True, scripts=True, javascript=True, links=True, meta=True)
            return cleaner.clean_html(data)
        except:
            return data

class SubParser(BaseParser):

    def __init__(self, inf):

        super(SubParser, self).__init__(inf)
        fm = self.inf['from']
        to  = self.inf['to']
        self.parse = partial(re.sub, fm, to)

class TextParser(BaseParser):

    def parse(self, data):
        if type(data) not in [str, unicode]:
            data = str(data)
        return remove_tags(data).strip()

class StrParser(BaseParser):

    def parse(self, data):
        if type(data) in [str, unicode]:
            return data.strip()

class FilterParser(BaseParser):

    def __call__(self, data):

        return [i for i in data if self.filter(i)]

    def filter(self, data):
        for k,v in self.inf.iteritems():
            if k=='type':
                continue
            elif k=='delta':
                now = datetime.utcnow()
                if not (type(data)==datetime and (now-data).total_seconds()<v):
                    return False
            elif k=='match':
                if not (type(data) in [str, unicode] and re.search(v, data)):
                    return False
            elif k=='min':
                if data<v:
                    return False
            elif k=='max':
                if data>v:
                    return False
            else:
                log.msg(u'invalid operator <{}>'.format(k), level=log.WARNING)
                continue
        return True

class CompParser(BaseParser):

    def __init__(self, inf):

        super(CompParser, self).__init__(inf)
        self.parsers = [make_parser(i) for i in self.inf]
        self.func = Compose(*self.parsers)

    def __call__(self, data):
        return self.func(data)

all_parsers = {
    cname[0:-6].lower():cls\
        for cname,cls in inspect.getmembers(sys.modules[__name__], inspect.isclass)\
            if issubclass(cls, BaseParser) and cname.endswith('Parser')
}

def make_parser(inf):

    if isinstance(inf, list):
        return CompParser(inf)
    elif isinstance(inf, str) or isinstance(inf, unicode):
        return make_parser({'type':inf})
    else:
        Parser = all_parsers.get(inf.get('type'), BaseParser)
        return Parser(inf)

if __name__=='__main__':

    data = ['<script>hello</script><p>   fff:oooo  </p>', 'b<i>bb</i>bb', 'foobar808foobar', u'今天::333', u'昨天']
    inf = [u'text', 'int', {'type':'filter', 'min':500}, 'head']
    parser = make_parser(inf)
    print data
    print parser(data)

