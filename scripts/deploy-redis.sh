#!/bin/bash

if [[ -f /usr/local/bin/redis-server ]]
then
    echo 'redis已安装'
    exit 1
fi

TMP=/tmp/deploy-redis
mkdir -p $TMP /etc/redis /var/{lib,log}/redis
cd $TMP

curl -O http://download.redis.io/releases/redis-stable.tar.gz

tar xzf redis-stable.tar.gz; cd redis-stable; make install

cat > /etc/redis/redis.conf <<-"_EOF_"
	# Redis configuration file example
	daemonize yes
	pidfile /var/run/redis.pid
	port 6379
	timeout 0
	tcp-keepalive 0
	loglevel notice
	logfile "/var/log/redis/redis.log"
	databases 16
	save 86400 1
	stop-writes-on-bgsave-error yes
	rdbcompression yes
	rdbchecksum yes
	dbfilename dump.rdb
	dir /var/lib/redis/
	slave-serve-stale-data yes
	slave-read-only yes
	repl-disable-tcp-nodelay no
	slave-priority 100
	appendonly no
	appendfsync everysec
	no-appendfsync-on-rewrite no
	auto-aof-rewrite-percentage 100
	auto-aof-rewrite-min-size 64mb
	lua-time-limit 5000
	slowlog-log-slower-than 10000
	slowlog-max-len 128
	notify-keyspace-events ""
	hash-max-ziplist-entries 512
	hash-max-ziplist-value 64
	list-max-ziplist-entries 512
	list-max-ziplist-value 64
	set-max-intset-entries 512
	zset-max-ziplist-entries 128
	zset-max-ziplist-value 64
	activerehashing yes
	client-output-buffer-limit normal 0 0 0
	client-output-buffer-limit slave 256mb 64mb 60
	client-output-buffer-limit pubsub 32mb 8mb 60
	hz 10
	aof-rewrite-incremental-fsync yes
	repl-timeout 500
_EOF_


cat > /etc/init.d/redis <<-"_EOF_"
	#!/bin/sh
	#
	# chkconfig: - 50 50
	#
	# Simple Redis init.d script conceived to work on Linux systems
	# as it does use of the /proc filesystem.
	
	REDISPORT=6379
	EXEC=/usr/local/bin/redis-server
	CLIEXEC=/usr/local/bin/redis-cli
	
	PIDFILE=/var/run/redis.pid
	CONF="/etc/redis/redis.conf"
	
	case "$1" in
	    start)
	        if [ -f $PIDFILE ]
	        then
	                echo "$PIDFILE exists, process is already running or crashed"
	        else
	                echo "Starting Redis server..."
	                $EXEC $CONF
	        fi
	        ;;
	    stop)
	        if [ ! -f $PIDFILE ]
	        then
	                echo "$PIDFILE does not exist, process is not running"
	        else
	                PID=$(cat $PIDFILE)
	                echo "Stopping ..."
	                $CLIEXEC -p $REDISPORT shutdown
	                while [ -x /proc/${PID} ]
	                do
	                    echo "Waiting for Redis to shutdown ..."
	                    sleep 1
	                done
	                echo "Redis stopped"
	        fi
	        ;;
	    *)
	        echo "Please use start or stop as first argument"
	        ;;
	esac
_EOF_

chmod +x /etc/init.d/redis

service redis start

chkconfig redis on

