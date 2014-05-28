#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from scrapy import signals, log
from scrapy.contrib.downloadermiddleware import retry
from scrapy.exceptions import IgnoreRequest, NotConfigured
from scrapy.http import Request
from urlparse import urlparse
from webbot.utils import utils
import random, re

# 随机切换代理
class ProxyMiddleware(object):

    def __init__(self, crawler):
        self.enabled = False
        self.proxy_list = []
        self.idx = 0
        self.cur = None
        crawler.signals.connect(self.spider_opened, signals.spider_opened)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def spider_opened(self, spider):
        try:
            if hasattr(spider, 'proxy'):
                m = re.match(r'^(http://[.0-9]+:[0-9]+)(,(http://[.0-9]+:[0-9]+))*$', spider.proxy)
                if m:
                    proxy = {
                        'list': spider.proxy.split(','),
                        'rate': 1
                    }
                else:
                    proxy = {
                        'file': spider.proxy,
                        'rate': 1
                    }
            else:
                proxy = {'enabled':False}

            self.enabled = proxy.get('enabled', True)
            if not self.enabled:
                return

            self.rate = proxy.get('rate', 10)

            for i in utils.load_keywords(proxy, msg='proxies'):
                m = re.match(r'^(?P<prot>\S+)(\s+|://)(?P<host>\S+)(\s+|:)(?P<port>\S+)$', i)
                if m:
                    self.proxy_list.append(m.groupdict())
                else:
                    log.msg('drop invalid proxy <{}>'.format(i), log.WARNING)

        except Exception as ex:
            self.enabled = False
            log.msg('cannot load proxies: {}'.format(ex))

    def process_request(self, request, spider):
        if self.proxy_bypass(request) or not (self.enabled and self.proxy_list):
            return
        self.idx += 1
        if (not self.cur) or self.idx>=self.rate:
            self.idx = 0
            proxy = random.choice(self.proxy_list)
            self.cur = '{0[prot]}://{0[host]}:{0[port]}'.format(proxy)
        request.meta['proxy'] = self.cur

    def proxy_bypass(self, request):
        return urlparse(request.url).hostname.startswith('192.168.')


# URL去除重复
class DedupMiddleware(object):

    def __init__(self, stats):
        self.stats = stats

    @classmethod
    def from_crawler(cls, crawler):
        o = cls(crawler.stats)
        crawler.signals.connect(o.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(o.spider_closed, signal=signals.spider_closed)
        return o

    def spider_opened(self, spider):
        if hasattr(spider, 'debug') and  spider.debug:
            spider.disabled.append('dedup')
            self.enabled = False
            return

        if hasattr(spider, 'dedup'):
            try:
                import redis
                uri = spider.dedup
                if not uri:
                    self.enabled = False
                    return

                log.msg('connect dedup <{}>'.format(uri))
                self.db = redis.StrictRedis.from_url(uri)
                self.db.ping()
                self.enabled = True
                return
            except Exception as ex:
                log.err('cannot connect dedup')

        self.enabled = False

    def process_request(self, request, spider):
        if self.enabled:
            url = request.url
            sha1 = utils.hash_url(url)
            try:
                if self.db.zrank('urlset', sha1) is not None:
                    log.msg('Dropped <url: {}> (hash: {})'.format(url, sha1), level=log.DEBUG)
                    self.stats.inc_value('item_duplicated_count', spider=spider)
                    raise IgnoreRequest()
            except IgnoreRequest as ex:
                raise
            except Exception as ex:
                self.stats.inc_value('redis/exception_count', spider=spider)

    def spider_closed(self, spider, reason):
        pass

# 非法请求过滤
class RequestMiddleware(object):

    def process_request(self, request, spider):
        url = request.url
        if url.startswith('http://0.0.0.0'):
            log.msg('ignore bad request', level=log.DEBUG)
            raise IgnoreRequest()

# 关键词接力(spidermw)
class KeywordRelayMiddleware(object):

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_spider_output(self, response, result, spider):
        kw = response.meta.get('keyword', '')
        for request in result:
            if isinstance(request, Request):
                request.meta['keyword'] = kw
            yield request

