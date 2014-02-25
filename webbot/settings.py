#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# A simple spider written by Kev++

BOT_NAME = 'webbot'
LOG_LEVEL = 'INFO'

SPIDER_MODULES = ['webbot.spiders']
NEWSPIDER_MODULE = 'webbot.spiders'

USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:26.0) Gecko/20100101 Firefox/26.0'

DEFAULT_REQUEST_HEADERS = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh,en;q=0.5',
        }

ITEM_PIPELINES = [
            'webbot.pipelines.BasicPipeline',
            'webbot.pipelines.DebugPipeline',
            'webbot.pipelines.MongoPipeline',
            'webbot.pipelines.MysqlPipeline',
            'webbot.pipelines.ZmqPipeline',
        ]

EXTENSIONS = {
            'scrapy.webservice.WebService': None,
            'scrapy.telnet.TelnetConsole': None,
            'webbot.extensions.StatsPoster': 999,
        }

DOWNLOADER_MIDDLEWARES = {
            'webbot.middlewares.DedupMiddleware': 999,
            'webbot.middlewares.ProxyMiddleware': 999,
            'scrapy.contrib.downloadermiddleware.retry.RetryMiddleware': None,
            'webbot.middlewares.RetryMiddleware': 500,
        }

SPIDER_MIDDLEWARES = {
        }

WEBSERVICE_ENABLED = False
TELNETCONSOLE_ENABLED = False
DOWNLOAD_TIMEOUT = 30
RETRY_TIMES = 2

DEFAULT_LOGGER = 'mongodb://192.168.3.175:27017/result.data'
DEFAULT_DEDUP = None

FEED_URI_PARAMS = 'webbot.utils.utils.feed_uri_params_parser'

