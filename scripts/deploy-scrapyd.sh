#!/bin/bash
# 在CentOS 6.5上安装scrapyd

# 安装程序

pip install scrapy==0.18.4 scrapyd

# 用户群组

useradd scrapy
groupadd nogroup
usermod -G nogroup scrapy

# 目录结构

mkdir -p /var/lib/scrapyd/{eggs,logs,dbs} /var/log/scrapyd
chown -R scrapy:nogroup /var/{lib,log}/scrapyd

# 配置文件

mkdir -p /etc/scrapyd
cat > /etc/scrapyd/scrapyd.conf <<-"__EOF__"
	
	[scrapyd]
	http_port       = 6800
	eggs_dir        = /var/lib/scrapyd/eggs
	logs_dir        = /var/lib/scrapyd/logs
	dbs_dir         = /var/lib/scrapyd/dbs
	items_dir       =
	poll_interval   = 0.25
	jobs_to_keep    = 10000
	finished_to_keep = 100
	max_proc_per_cpu = 16
	
__EOF__

# 启动脚本

cat > /etc/init/scrapyd.conf <<-"__EOF__"
	
	# Scrapy service
	start on runlevel [2345]
	stop on runlevel [06]
	
	script
	    [ -r /etc/default/scrapyd ] && . /etc/default/scrapyd
	    logdir=/var/log/scrapyd
	    exec scrapyd -u scrapy -g nogroup \
	                --pidfile /var/run/scrapyd.pid \
	                -l $logdir/scrapyd.log >$logdir/scrapyd.out 2>$logdir/scrapyd.err
	end script
	
__EOF__

# 启动服务

start scrapyd

