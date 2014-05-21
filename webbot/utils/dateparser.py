#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from collections import OrderedDict
import re

__all__ = ['parse_date', 'tz_offset']

def parse_date(x, fmt='auto', tz='+00:00'):

    """
    Parse datetime `x` with format `fmt` and timezone `tz`.

    :param x: datetime string
    :type x: str
    :param fmt: datetime format
    :type fmt: str
    :param tz: timezone
    :type fmt: str
    """

    try:

        x = unicode(x)
        fmt = unicode(fmt)

        utcnow = datetime.utcnow()
        offset = tz_offset(tz)
        now = utcnow + offset

        if fmt=='auto':
            date = _parse(x, now)
        elif fmt in ['epoch', 'unix']:
            date = datetime.utcfromtimestamp(int(x))
            offset = timedelta(0)
        else:
            date = datetime.strptime(x.encode('utf-8'), fmt.encode('utf-8'))

        return date - offset

    except:
        #import traceback
        #traceback.print_exc()
        return datetime.utcfromtimestamp(0)

def tz_offset(tz):

    tz = tz.lower().strip()
    if tz=='cst':
        offset = timedelta(hours=8)
    elif tz=='utc':
        offset = timedelta()
    else:
        res = re.search(r'(?P<F>[-+])(?P<HH>\d{2}):?(?P<MM>\d{2})', tz).groupdict()
        offset = timedelta(
                     hours   = int(res['HH']),
                     minutes = int(res['MM'])
                 ) * (1 if res.get('F', '+')=='+' else -1)

    return offset

def _parse(x, now=None):

    # 当前时间
    now = now or datetime.utcnow()
    now_SS = date_scale(now, 'SS')
    now_MM = date_scale(now, 'MM')
    now_HH = date_scale(now, 'HH')
    now_dd = date_scale(now, 'dd')
    now_mm = date_scale(now, 'mm')
    now_YY = date_scale(now, 'YY')

    # 单位时间
    one_SS = timedelta(seconds=1)
    one_MM = timedelta(minutes=1)
    one_HH = timedelta(hours=1)
    one_dd = timedelta(days=1)
    one_ww = timedelta(days=7)
    one_mm = timedelta(days=30)
    one_YY = timedelta(days=365)

    # 预处理
    x = re.sub(u'刚刚|刚才', now_MM.strftime(' %F %T '), x)
    x = re.sub(u'几', u'0', x)
    x = re.sub(ur'(?<=[\d半前昨今明后])(天|号)', u'日', x)

    rdays = {
        u'前日': now_dd-one_dd*2,
        u'昨日': now_dd-one_dd*1,
        u'今日': now_dd,
        u'明日': now_dd+one_dd*1,
        u'后日': now_dd+one_dd*2,
    }

    for k,v in rdays.iteritems():
        x = x.replace(k, v.strftime(' %F '))

    x = re.sub(ur'(?<=\d)[/.](?=\d)', u'-', x)
    x = re.sub(ur'[^-:\s\d前半秒分时日周月年]', '', x)
    x = re.sub(ur'(?<![\d\s])\s+(?![\d\s])', '', x)
    x = re.sub(ur'(?<!年)(?=(\d+)月(\d+)日)', u' %d年'%now.year, x)
    x = re.sub(ur'(\d+)年(\d+)月(\d+)日', r'\g<1>-\g<2>-\g<3>', x)
    x = x.strip()

    if '-' in x or ':' in x:

        parts = {}
        pats = [
            ur'(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})',
            ur'(?P<hour>\d{1,2}):(?P<minute>\d{1,2})(:(?P<second>\d{1,2}))?',
        ]
        for p in pats:
            m = re.search(p, x)
            if m:
                parts.update(m.groupdict())

        for k,v in parts.items():
            if v==None:
                del parts[k]
            else:
                parts[k] = int(v)

        if parts:

            parts['year'] = parts.get('year', now.year)
            parts['month'] = parts.get('month', now.month)
            parts['day'] = parts.get('day', now.day)

            return datetime(**parts)

    if u'半' in x:

        halves = {
            u'半分': u'30秒',
            u'半时': u'30分',
            u'半日': u'12时',
            u'半周': u'84时',
            u'半月': u'15日',
            u'半年': u'6月',
        }

        for k,v in halves.iteritems():
            x = re.sub(k, v, x)

    if u'前' in x:

        rpats = [
            ur'(?P<years>\d+)年前',
            ur'(?P<months>\d+)月前',
            ur'(?P<weeks>\d+)周前',
            ur'(?P<days>\d+)日前',
            ur'(?P<hours>\d+)时前',
            ur'(?P<minutes>\d+)分前',
            ur'(?P<seconds>\d+)秒前',
        ]

        for p in rpats:
            m = re.search(p, x)
            if m:
                d = m.groupdict()
                k = d.keys()[0]
                v = int(d.values()[0])
                if k == 'years':
                    date = date_scale(now_YY - one_YY*v, 'YY')
                elif k == 'months':
                    date = date_scale(now_mm - one_mm*v, 'mm')
                elif k == 'weeks':
                    date = date_scale(now_dd - one_ww*v, 'dd')
                elif k == 'days':
                    date = date_scale(now_dd - one_dd*v, 'dd')
                elif k == 'hours':
                    date = date_scale(now_HH - one_HH*v, 'HH')
                elif k == 'minutes':
                    date = date_scale(now_MM - one_MM*v, 'MM')
                elif k == 'seconds':
                    date = date_scale(now_SS - one_SS*v, 'SS')
                else:
                    raise Exception()
                return date

    for i in re.findall(ur'(?<!\d)((?:19|20)\d{6}|1\d{9}|1\d{12})(?!\d)', x):
        k = len(i)
        v = int(i)
        if k == 8:
            date = datetime.strptime(i, '%Y%m%d')
        elif k == 10:
            date = datetime.fromtimestamp(v)
        elif k == 13:
            date = datetime.fromtimestamp(v/1000)
        else:
            raise Exception()
        return date

    raise Exception()

def date_scale(dt, scale='MM'):

    scales = OrderedDict([
        ('MS','microsecond'),
        ('SS','second'),
        ('MM','minute'),
        ('HH','hour'),
        ('dd','day'),
        ('mm','month'),
        ('YY','year'),
    ])

    assert scale in scales
    
    for k,v in scales.iteritems():
        if k==scale:
            return dt
        dt = dt.replace(**{v:1 if k in ['dd', 'mm'] else 0})

    raise Exception()

if __name__ == '__main__':

    xs = [
        u'2014-01-01',
        u'2014/01/01',
        u'2014.01.01',

        u'01:23',
        u'01:23:45',
        u'01 : 23 : 45',

        u'2014-01-01 01:23',
        u'2014-01-01 01:23:45',

        u'今天',
        u'昨天',
        u'前天',

        u'刚刚',
        u'刚才',
        u'几秒前',
        u'5秒前',

        u'5分钟前',
        u'5小时前',
        u'5天前',
        u'5周前',
        u'5年前',

        u'半分钟前',
        u'半小时前',
        u'半天前',
        u'半周前',
        u'半月前',
        u'半年前',

        u'20140101',
        u'20140101 012345',

        u'1400641135',
        u'1400641135000',

        u'4月19号的预售，今天都5月21号了',
        u'刚才 你去哪了？',
    ]

    for i, x in enumerate(xs):
        print 'IN [%d]: %s' % (i, x)
        y = parse_date(x, 'auto', 'cst')
        print 'OUT[%d]: %s [%s]' % (i, y, type(y).__name__)
        print

    print parse_date('01012014080000', '%m%d%Y%H%M%S', '+08:00')
    print parse_date('1400657331', 'epoch', '+08:00')

