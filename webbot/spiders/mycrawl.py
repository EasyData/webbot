#!/usr/bin/env python
# -*- coding: utf-8 -*-

from scrapy.http import Request, HtmlResponse
from scrapy.contrib.spiders import CrawlSpider, Rule

import inspect

class MyCrawlSpider(CrawlSpider):

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

