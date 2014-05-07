#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from cssselect.xpath import HTMLTranslator
from scrapy import log
from scrapy.contrib.linkextractors.sgml import SgmlLinkExtractor
from scrapy.contrib.loader import ItemLoader
from scrapy.contrib.spiders import CrawlSpider, Rule
from scrapy.exceptions import CloseSpider
from scrapy.http import Request, FormRequest, HtmlResponse
from scrapy.item import Item, Field
from scrapy.selector import Selector
from scrapy.utils.datatypes import CaselessDict
from scrapy.utils.misc import arg_to_iter
from urllib2 import urlparse
from webbot import settings
from webbot.utils import parser
from webbot.utils import utils
import Cookie
import inspect
import json
import jsonpath
import re
import traceback

class WebbotSpider(CrawlSpider):

    name = 'webbot'

    def __init__(self, config=None, debug=None, verbose=0, **kwargs):

        super(WebbotSpider, self).__init__()

        if not config:
            return

        self.disabled = []
        self.config = config
        self.debug = debug
        self.verbose = int(verbose)
        self.tz = kwargs.get('tz', '+00:00')
        self.conf = self.load_config()
        self.debug_mode()

    def start_requests(self):

        self.print_msg()

        for i in CrawlSpider.start_requests(self):
            yield i

    def debug_mode(self):

        self.debug = str(self.debug).upper()=='TRUE'
        if not self.debug:
            return

        for db in ['mongo', 'mysql', 'zmq']:
            if hasattr(self, db):
                delattr(self, db)
                self.disabled.append(db)

    def print_msg(self):

        if self.debug:
            self.log(utils.G(u'{:=^20}'.format(' DEBUG MODE ')), level=log.WARNING)
            for i in self.disabled:
                self.log(utils.Y(u'disable {}'.format(i)), level=log.WARNING)

        self.log(u'loading config from <{}>:\n{}'.format(unicode(self.config, encoding='utf-8'),
            json.dumps(self.conf, indent=2, ensure_ascii=False, sort_keys=True)), level=log.INFO)

    def load_config(self):

        conf = utils.load_cfg(self.config)

        ### debug
        if self.debug==None:
            self.debug = conf.get('debug', False)

        ### site
        self.site = conf.get('site', u'未知站点')
        self.macro = utils.MacroExpander({
            'SITE': self.site,
            'CONF': json.dumps(conf)
        })

        ### allowed_domains
        self.allowed_domains = conf.get('domains', [])

        ### start_urls
        urls = conf.get('urls', [])
        self.start_urls = utils.generate_urls(urls, self.macro)
        if isinstance(urls, dict):
            self.start_method = urls.get('method', 'GET')
            self.make_headers(urls.get('headers', {}))
            if urls.get('parse'):
                self.parse_start_url = self.parse_page
        else:
            self.start_method = 'GET'
            self.make_headers({})

        ### rules
        self.tr = HTMLTranslator()
        self.rules = []
        self.page_extractor = None
        for k,v in conf.get('rules', {}).iteritems():

            follow = v.get('follow', True)
            callback = None if follow else 'parse_page'
            follow = True if follow is None else follow
            regex = self.macro.expand(v.get('regex'))
            css = self.macro.expand(v.get('css'))
            if css:
                xpath = self.tr.css_to_xpath(css)
            else:
                xpath = self.macro.expand(v.get('xpath'))
            pages = v.get('pages')
            sub = v.get('sub')
            vars = v.get('vars')

            rule = Rule(
                SgmlLinkExtractor(
                    allow=regex,
                    restrict_xpaths=xpath,
                    process_value=utils.first_n_pages(regex, pages)
                ),
                process_links=self.sub_links(sub),
                process_request=self.set_vars(k, vars),
                callback=callback,
                follow=follow
            )

            self.rules.append(rule)
        self._compile_rules()

        if not self.rules:
            self.parse_start_url = self.parse_page
            self.make_page_extractor(conf.get('urls', []))

        ### mappings(loop/fields)
        self.build_item(conf)

        ### settings
        self.load_settings(conf)

        return conf

    def load_settings(self, conf):

        self.logger = settings.DEFAULT_LOGGER
        self.dedup = settings.DEFAULT_DEDUP

        for k,v in conf.get('settings', {}).iteritems():
            log.msg(utils.G('+SET {} = {}'.format(k, v)))
            setattr(self, k, v)

        ### parser(html/json)
        if hasattr(self, 'spider') and 'json' in self.spider:
            self.parse_item = self.parse_json_item
        else:
            self.parse_item = self.parse_html_item

        ### plugin
        if hasattr(self, 'plugin'):
            self.plugin = utils.load_plugin(self.plugin)
            self.plugin.spider = self
        else:
            self.plugin = None

    def build_item(self, conf):

        self.fields = conf['fields']

        for k,v in self.fields.iteritems():
            Item.fields[k] = Field()
            for i,j in v.iteritems():
                Item.fields[k][i] = j

        if 'image_urls' in Item.fields:
            Item.fields['images'] = Field()
            Item.fields['images']['multi'] = True
            Item.fields['image_urls']['multi'] = True

        self.loop = self.macro.expand(conf.get('loop', ''))
        if self.loop.startswith('css:'):
            self.loop = self.tr.css_to_xpath(loop[len('css:'):])

    def make_requests_from_url(self, url):

        kw = self.macro.query(url)
        us = urlparse.urlsplit(url)
        qstr = dict(urlparse.parse_qsl(us.query))
        base = urlparse.urlunsplit(us._replace(query=''))
        meta = {'keyword':kw}
        return FormRequest(base, formdata=qstr, method=self.start_method, headers=self.headers, cookies=self.cookies, dont_filter=True, meta=meta)

    def run_plugin(self, response):

        if response.meta.get('dirty')==False:
            return response.replace(url=response.meta.get('url', response.url))
        elif self.plugin:
            output = self.plugin.parse(
                url=response.url,
                body=response.body,
                meta=response.meta,
                status=response.status,
                headers=response.headers
            )
            if isinstance(output, Request):
                output.meta['dirty'] = False
                return output.replace(callback=self.parse_page)
            else:
                return response.replace(body=output)
        else:
            return response

    def parse_page(self, response):

        try:
            response = self.run_plugin(response)

            if isinstance(response, Request):
                yield response
                return

            for item in self.parse_item(response, self.loop, self.fields):
                yield item

            if self.page_extractor:
                for link in self.page_extractor.extract_links(response):
                    yield Request(link.url, meta=response.meta)

        except Exception as ex:

            log.msg(u'{}\n{}'.format(response.url, traceback.format_exc()))

    def parse_json_item(self, response, loop, fields):

        txt = utils.to_unicode(response.body)
        if hasattr(self, 'json_type') and self.json_type=='list':
            l, r = txt.find('['), txt.rfind(']')
        else:
            l, r = txt.find('{'), txt.rfind('}')
        obj = json.loads(txt[l:r+1])
        self.macro.update({'URL':response.url})

        for e in jsonpath.jsonpath(obj, loop or '$[]') or []:

            item = Item()

            for k,v in fields.iteritems():
                if 'value' in v:
                    v_x = v.get('value')
                elif 'jpath' in v:
                    v_x = jsonpath.jsonpath(e, self.macro.expand(v.get('jpath')))
                else:
                    log.msg(u'field [{}] should contains "value" or "jpath"'.format(k), level=log.WARNING)
                    continue

                val = parser.make_parser(v.get('parse', {}))([self.macro.expand(v_x)])

                if not val and 'default' in v:
                    val = self.macro.expand(v.get('default'))

                item[k] = arg_to_iter(val)

            else:

                yield item

    def parse_html_item(self, response, loop, fields):

        meta = response.meta
        hxs = Selector(response)
        self.macro.update({'URL':response.url, 'keyword':meta.get('keyword', '')})

        for e in hxs.xpath(loop or '(//*)[1]'):

            loader = ItemLoader(item=Item(), selector=e)

            for k,v in fields.iteritems():

                if 'value' in v:
                    get_v_x = loader.get_value
                    v_x = v.get('value')
                elif 'css' in v:
                    get_v_x = loader.get_css
                    v_x = v.get('css')
                elif 'xpath' in v:
                    get_v_x = loader.get_xpath
                    v_x = v.get('xpath')
                else:
                    log.msg(u'field [{}] should contains "value", "xpath" or "css"'.format(k), level=log.WARNING)
                    continue

                val = get_v_x(
                    self.macro.expand(v_x, meta),
                    parser.make_parser(v.get('parse', {})),
                    re=v.get('regex')
                )

                if not val and 'default' in v:
                    val = arg_to_iter(self.macro.expand(v.get('default'), meta))

                if not val and 'multi' not in v:
                    break

                loader.add_value(k, val)

            else:

                yield loader.load_item()

    def sub_links(self, sub):

        if not sub:
            return None

        frm = sub.get('from')
        to = sub.get('to')

        def _sub(links):

            new_links = []
            for i in links:
                i.url = re.sub(frm, to, i.url)
                new_links.append(i)
            return new_links

        return _sub

    def set_vars(self, key, vars):

        if not vars:
            return lambda x:x

        def _proc(request, response):
            meta = request.meta
            hxs = Selector(response)
            for k,v in vars.iteritems():
                if k.isupper():
                    meta[k] = (hxs.xpath(v).extract() or [''])[0]
            return request

        return _proc

    # TODO: should persistent accross session
    def make_headers(self, headers):

        headers = CaselessDict(headers)
        if 'user-agent' in headers:
            self.user_agent = headers.pop('user-agent')
        self.cookies = self.make_cookies(headers.pop('cookie', {}))
        self.headers = headers

    def make_cookies(self, cookies):

        if type(cookies) == unicode:
            cookies = cookies.encode('utf-8')
        if type(cookies)==str:
            cookies = {i.key:i.value for i in Cookie.SimpleCookie(cookies).values()}
        elif type(cookies)==dict:
            cookies = cookies
        else:
            cookies = {}
        return cookies

    def make_page_extractor(self, obj):

        if type(obj)!=dict:
            return

        pages = obj.get('pages')
        if pages:
            regex = self.macro.expand(pages.get('regex'))
            css = self.macro.expand(pages.get('css'))
            if css:
                xpath = self.tr.css_to_xpath(css)
            else:
                xpath = self.macro.expand(pages.get('xpath'))
            self.page_extractor = SgmlLinkExtractor(
                allow=regex,
                restrict_xpaths=xpath,
                process_value=utils.first_n_pages(regex, pages)
            )

    # HACK
    def _requests_to_follow(self, response):

        if not isinstance(response, HtmlResponse):
            return

        meta = {k:v for k,v in response.meta.iteritems() if k.isupper()}
        seen = set()

        for n, rule in enumerate(self._rules):

            links = [l for l in rule.link_extractor.extract_links(response) if l not in seen]
            if links and rule.process_links:
                links = rule.process_links(links)
            seen = seen.union(links)

            for link in links:

                r = Request(url=link.url, callback=self._response_downloaded)
                r.meta.update(rule=n, link_text=link.text)
                r.meta.update(meta)

                fun = rule.process_request
                if not hasattr(fun, 'nargs'):
                    fun.nargs = len(inspect.getargs(fun.func_code).args)
                if fun.nargs==1:
                    yield fun(r)
                elif fun.nargs==2:
                    yield fun(r, response)
                else:
                    raise Exception('too many arguments')

