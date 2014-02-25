#!/usr/bin/env python

import redis
import time
from datetime import datetime, timedelta

db = redis.StrictRedis(host='192.168.94.3')
now = datetime.now()
ago = now - timedelta(days=7)

tot = db.zcard('urlset2')

cur = idx = cnt = 0

while True:

    cur, items = db.zscan('urlset2', cur)
    idx += len(items)

    if idx>1e4:
        idx = 0
        print datetime.now(), cnt, '/', tot

    for k,v in items:
        dt = datetime.fromtimestamp(v)
        if dt<ago:
            with db.pipeline() as p:
                p.zrem('urlset', k)
                p.zrem('urlset2', k)
                p.delete(k)
                p.execute()
                cnt += 1

    if cur==0:
        break

