#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import re

def tz_offset(tz):
    res = (re.search(r'(?P<F>[-+])(?P<H>\d{2}):?(?P<M>\d{2})', tz) or re.search('', '')).groupdict()
    offset = (1 if res.get('F', '+')=='+' else -1) * timedelta(
                        hours   = int(res.get('H', 0)),
                        minutes = int(res.get('M', 0)))
    return offset

def parse_date(data, fmt, tz):
    offset = tz_offset(tz)

    if fmt=='auto':
        now = datetime.utcnow().replace(microsecond=0)+offset
        now_1 = now-timedelta(days=1)
        now_2 = now-timedelta(days=2)

        # 几/刚/今天/昨天/前天
        x = data.strip()
        x = x.replace(u'\xa0', ' ')
        x = x.replace(u'几', ' 0 ')
        x = re.sub(ur'刚[刚才]', now.strftime(' %Y-%m-%d %H:%M:%S '), x)
        x = re.sub(ur'今[天日]', now.strftime(' %Y-%m-%d '), x)
        x = re.sub(ur'昨[天日]', now_1.strftime(' %Y-%m-%d '), x)
        x = re.sub(ur'前[天日]', now_2.strftime(' %Y-%m-%d '), x)
        x = re.sub(ur'[年月]',  '/', x)
        x = re.sub(ur'[日]',    ' ', x)
        x = re.sub(ur'半\s*[天日]前',  u'12小时前', x)
        x = re.sub(ur'半\s*小?时前', u'30分钟前', x)
        x = re.sub(ur'半\s*分钟前', u'30秒钟前', x)
        x = re.sub(ur'\s{2,}', r' ', x)

        # XX前
        res = ( re.search(ur'(?P<S>\d+)\s*秒钟?前', x) \
             or re.search(ur'(?P<M>\d+)\s*分钟前', x) \
             or re.search(ur'(?P<H>\d+)\s*小?时前', x) \
             or re.search(ur'(?P<d>\d+)\s*[天日]前', x) \
             or re.search('', '')).groupdict()

        if res:
            dt = now - timedelta(
                                days    = int(res.get('d', 0)),
                                hours   = int(res.get('H', 0)),
                                minutes = int(res.get('M', 0)),
                                seconds = int(res.get('S', 0))
                              )
        else:
            # XX-XX-XX XX:XX:XX
            res = ( re.search(ur'(?P<Y>\d+)[/-](?P<m>\d+)[/-](?P<d>\d+)(\s+(?P<H>\d{2}):(?P<M>\d{2})(:(?P<S>\d{2}))?)?', x) \
                 or re.search('', '')).groupdict()

            if res:
                Y = res.get('Y', now.year)
                m = res.get('m', now.month)
                d = res.get('d', now.day)
                H = res.get('H', now.hour)
                M = res.get('M', now.minute)
                S = res.get('S', 0)

                dt = datetime(
                            year   = int(Y) if Y!=None else now.year,
                            month  = int(m) if m!=None else now.month,
                            day    = int(d) if d!=None else now.day,
                            hour   = int(H) if H!=None else now.hour,
                            minute = int(M) if M!=None else now.minute,
                            second = int(S) if S!=None else 0
                        )
            else:
                # 1970-01-01 00:00:00
                dt = datetime.utcfromtimestamp(0)+offset

    # UNIX TIMESTAMP
    elif fmt=='unix':
        dt = datetime.utcfromtimestamp(int(data))
        offset = timedelta(0)
    else:
        dt = datetime.strptime(unicode(data).encode('utf-8'), unicode(fmt).encode('utf-8'))

    return dt-offset

