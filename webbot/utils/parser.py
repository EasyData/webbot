#!/usr/bin/env python
# -*- coding: utf-8 -*-

from functools import partial
from scrapy.contrib.loader.processor import *
from scrapy.utils.markup import remove_tags
from lxml.html.clean import Cleaner
from webbot.utils.utils import parse_date
import inspect
import re
import sys
import base64

# float
# http
# int
# jpath
# map
# unesc
# xpath

class BaseParser(object):

    def __init__(self, inf):

        assert self.__class__.__name__.endswith('Parser')
        self.inf = inf

    def parse(self, data):

        return data
    
    def __call__(self, data):

        return MapCompose(self.parse)(data)

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

class DateParser(BaseParser):

    def parse(self, data):

        fmt = self.inf.get('fmt', 'auto')
        tz = self.inf.get('tz', '+00:00')
        return parse_date(data, fmt, tz)

class CstParser(BaseParser):

    def parse(self, data):

        fmt = self.inf.get('fmt', 'auto')
        tz = self.inf.get('tz', '+00:00')
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

class CompParser(BaseParser):

    def __init__(self, inf):

        super(CompParser, self).__init__(inf)

    def __call__(self, data):
        return Compose(*[make_parser(i) for i in self.inf])(data)

all_parsers = {
    cname[0:-6].lower():cls\
        for cname,cls in inspect.getmembers(sys.modules[__name__], inspect.isclass)\
            if issubclass(cls, BaseParser) and cname.endswith('Parser')
}

def make_parser(inf):

    if isinstance(inf, list):
        return CompParser(inf)
    else:
        Parser = all_parsers.get(inf.get('type'), BaseParser)
        return Parser(inf)

if __name__=='__main__':

    data = ['<script>hello</script><p>   fffoooo  </p>', 'b<i>bb</i>bb', 'foobarfoobar']
    inf = [{'type':'text'}, {'type':'join'}]
    parser = make_parser(inf)
    print data
    print parser(data)

