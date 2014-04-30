#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from datetime import datetime
from scrapy import log
from scrapy.contrib.pipeline.images import ImagesPipeline
from scrapy.exceptions import DropItem
from scrapy.item import Item, Field
from webbot.utils import utils, dateparser
import pprint
import re
import traceback


# 字段映射(mapping)
def item2post(item):

    post = {}
    for k,v in item.fields.iteritems():
        if 'name' in v:
            post[v['name']] = item[k]
    return post


# 基本处理(basic)
class BasicPipeline(object):

    def open_spider(self, spider):
        self.img = 'image_urls' in Item.fields

    def process_item(self, item, spider):
        try:
            for k,v in item.fields.iteritems():
                if v.get('multi'):
                    pass
                elif isinstance(item[k], list):
                    item[k] = item[k][0]
            return item
        except Exception as ex:
            raise DropItem('item error: {}'.format(ex))


# 调试打印(debug)
class DebugPipeline(object):

    def open_spider(self, spider):

        self.printer = utils.UnicodePrinter(getattr(spider, 'verbose', 0))
        self.idx = 0

    def process_item(self, item, spider):
        if not (hasattr(spider, 'debug') and spider.debug):
            return item

        self.idx += 1
        print utils.B('{:=^30}').format(self.idx)
        for k,v in item.iteritems():
            if type(v) in [str, unicode]:
                v = re.sub(r'\s{2,}', ' ', v.replace('\n', ' ').replace('\r', ''))
                if spider.verbose<3:
                    v = self.printer.squeeze(v)
            elif type(v)==datetime:
                now = datetime.utcnow()
                if v>now:
                    colored = utils.RR
                elif (now-v).total_seconds()>24*3600:
                    colored = utils.R
                else:
                    colored = lambda x:x
                offset = dateparser.tz_offset(spider.tz)
                v = colored(v + offset)
            else:
                v = re.sub(r'(?m)^', '{: ^13}'.format(''), self.printer.pformat(v)).decode('utf-8').strip()
            f = ' ' if 'name' in item.fields[k] else '*'
            print u'{:>10.10}{}: {}'.format(k, f, v).encode('utf-8')

        return item


# 数据存储(mongo)
class MongoPipeline(object):

    def open_spider(self, spider):
        if hasattr(spider, 'mongo'):
            try:
                self.upsert_keys = self.get_upsert_keys()
                uri = spider.mongo
                log.msg('connect <{}>'.format(uri))
                self.cnn, self.db, self.tbl = utils.connect_uri(uri)
                return
            except Exception as ex:
                log.err('cannot connect to mongodb: {}'.format(ex))

        self.cnn = self.db = None

    def get_upsert_keys(self):
        keys = []
        for k,v in Item.fields.iteritems():
            if 'name' in v and v.get('upsert'):
                keys.append(v['name'])
        return keys

    def process_item(self, item, spider):
        if self.cnn:
            try:
                post = item2post(item)
                if self.upsert_keys:
                    criteria = {k:post[k] for k in self.upsert_keys}
                    self.tbl.update(criteria, post, upsert=True)
                else:
                    self.tbl.insert(post)
            except Exception as ex:
                traceback.print_exc()
        return item

    def close_spider(self, spider):
        if self.cnn:
            log.msg('disconnect mongodb')
            self.cnn.close()
            self.cnn = None


# 数据存储(mysql)
class MysqlPipeline(object):

    def open_spider(self, spider):
        if hasattr(spider, 'mysql'):
            try:
                uri = spider.mysql
                log.msg('connect <{}>'.format(uri))
                self.cnn, _, self.tbl = utils.connect_uri(uri)
                self.cur = self.cnn.cursor()
                return
            except Exception as ex:
                traceback.print_exc()
                log.err('cannot connect to mysql: {}'.format(ex))

        self.cnn = self.cur = None

    def process_item(self, item, spider):
        if self.cnn:
            try:
                post = item2post(item)
                fields = []
                values = []
                for k,v in post.iteritems():
                    fields.append(k)
                    values.append(v)

                self.cur.execute(
                    """INSERT INTO {}({}) VALUES({});""".format(
                        self.tbl,
                        ','.join(fields),
                        ','.join(['%s']*len(fields))
                    ),
                    values
                )

                self.cnn.commit()
            except Exception as ex:
                traceback.print_exc()
        return item

    def close_spider(self, spider):
        if self.cnn:
            log.msg('disconnect mysql')
            self.cur.close()
            self.cnn.close()
            self.cnn = self.cur = None


# 消息队列(zmq)
class ZmqPipeline(object):

    def open_spider(self, spider):
        if hasattr(spider, 'zmq'):
            try:
                from utils.api import MessageSender
                uri = spider.zmq
                log.msg('connect <{}>'.format(uri))
                self.sender = MessageSender(uri)
                return
            except Exception as ex:
                log.err('cannot connect to zmq: {}'.format(ex))

        self.sender = None

    def process_item(self, item, spider):
        if self.sender:
            try:
                self.sender.send(item2post(item))
            except Exception as ex:
                traceback.print_exc()
        return item

    def close_spider(self, spider):
        if self.sender:
            log.msg('disconnect zmq')
            self.sender.term()


# 图片下载(img)
class ImgPipeline(ImagesPipeline):

    def open_spider(self, spider):

        self.img = 'image_urls' in Item.fields
        self.spiderinfo = self.SpiderInfo(spider)
        if hasattr(spider, 'img'):
            self.store = self._get_store(spider.img)

    def process_item(self, item, spider):

        if self.img:
            return ImagesPipeline.process_item(self, item, spider)
        else:
            return item

    def get_media_requests(self, item, info):

        for r in ImagesPipeline.get_media_requests(self, item, info):
            r.headers['Referer'] = item.get('url', 'http://www.google.com')
            yield r

