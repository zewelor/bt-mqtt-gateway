#!/bin/sh

if ! [ -f '/application/config.yaml' ]; then
    echo "There is no config.yaml! Check example config: https://github.com/zewelor/bt-mqtt-gateway/blob/master/config.yaml.example"
    exit 1
fi

if [ "$DEBUG" = 'true' ]; then
    echo "Start in debug mode"
    python3 ./gateway.py -d
    status=$?
    echo "Gateway died..."
    exit $status
else
    echo "Start in normal mode"
    python3 ./gateway.py
fi
