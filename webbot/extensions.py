#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from scrapy import signals
from scrapy import log
from datetime import datetime
from webbot.utils import utils
import os

class StatsPoster(object):

    def __init__(self, crawler):
        self.crawler = crawler
        self.stats = crawler.stats

    @classmethod
    def from_crawler(cls, crawler):
        o = cls(crawler)
        crawler.signals.connect(o.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(o.spider_closed, signal=signals.spider_closed)
        return o

    def spider_opened(self, spider):
        pass

    def spider_closed(self, spider, reason):
        if hasattr(spider, 'debug') and spider.debug:
            log.msg(utils.Y(u'disable logger'), level=log.WARNING)
            return

        if hasattr(spider, 'logger'):
            try:
                from pymongo import uri_parser, MongoClient
                uri = spider.logger
                if not uri:
                    return

                log.msg('post bot stats to <{}>'.format(uri))
                cnn, db, tbl = utils.connect_uri(uri)

                ago = self.stats.get_value('start_time', datetime.utcnow())
                now = datetime.utcnow()

                self.stats.set_value('finish_time', now, spider=spider)
                self.stats.set_value('elapsed_time', (now-ago).total_seconds(), spider=spider)
                self.stats.set_value('finish_reason', reason, spider=spider)
                self.stats.set_value('bot_ip', utils.get_ipaddr('eth0'))
                self.stats.set_value('bot_name', self.crawler.settings.get('BOT_NAME', 'unknown'))
                self.stats.set_value('spider_name', spider.name)
                self.stats.set_value('config_path', spider.config)
                self.stats.set_value('job_id', os.getenv('SCRAPY_JOB', None))

                tbl.insert({k.replace('.', '_'):v for k,v in self.stats.get_stats().iteritems()})
                cnn.close()
            except Exception as ex:
                log.err('cannot post bot stats')

