#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# Define your item pipelines here

from scrapy import log
from scrapy.exceptions import DropItem
from datetime import datetime
from webbot.utils import utils
import re, traceback


def item2post(item):
    post = {}
    for k,v in item.fields.iteritems():
        if 'name' in v:
            post[v['name']] = item[k]
    return post


class BasicPipeline(object):
    def process_item(self, item, spider):
        try:
            for k,v in item.fields.iteritems():
                if type(item[k])==list:
                    item[k] = item[k][0]
            return item
        except Exception as ex:
            raise DropItem('item error: {}'.format(ex))


class DebugPipeline(object):
    def open_spider(self, spider):
        self.idx = 0

    def process_item(self, item, spider):
        if not (hasattr(spider, 'debug') and spider.debug):
            return item

        self.idx += 1
        print utils.B('{:=^30}'.format(self.idx))
        for k,v in item.iteritems():
            if type(v) in [str, unicode]:
                v = re.sub(r'\s{2,}', ' ', v.replace('\n', ' ').replace('\r', ''))
                if spider.verbose<3 and len(v)>74:
                    v = u'{} {} {}'.format(v[:60].strip(), utils.B(u'……'), v[-14:].strip())
            elif type(v)==datetime:
                now = datetime.utcnow()
                if v>now:
                    colored = utils.RR
                elif (now-v).total_seconds()>24*3600:
                    colored = utils.R
                else:
                    colored = lambda x:x
                offset = utils.tz_offset(spider.tz)
                v = colored(v + offset)
            f = ' ' if 'name' in item.fields[k] else '*'
            print u'{:>10.10}{}: {}'.format(k, f, v).encode('utf-8')

        return item


# 数据存储(mongo)
class MongoPipeline(object):
    def open_spider(self, spider):
        if hasattr(spider, 'mongo'):
            try:
                uri = spider.mongo
                log.msg('connect <{}>'.format(uri))
                self.cnn, self.db, self.tbl = utils.connect_uri(uri)
                return
            except Exception as ex:
                log.err('cannot connect to mongodb: {}'.format(ex))

        self.cnn = self.db = None

    def process_item(self, item, spider):
        if self.cnn:
            try:
                post = item2post(item)
                if '_id' in post:
                    self.tbl.update({'_id':post['_id']}, post, {'upsert':True})
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
                self.cur.execute("""INSERT INTO {}({}) VALUES({});""".format(
                                                                                self.tbl,
                                                                                ','.join(fields),
                                                                                ','.join(['%s']*len(fields))
                                                                            ), values)
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

