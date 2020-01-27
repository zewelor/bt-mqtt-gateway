#!/bin/sh

if ! [ -f '/config.yaml' ]; then
    echo "There is no config.yaml! An example is created."
    cp /application/config.yaml.example /config.yaml.example
    exit 1
fi

cd /application
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
