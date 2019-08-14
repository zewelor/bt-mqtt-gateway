#!/bin/sh
set -e
SCRIPT_DIR=$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )
VIRTUAL_ENV=$SCRIPT_DIR/.venv
if [ -d "$VIRTUAL_ENV" ]; then
    export VIRTUAL_ENV
    PATH="$VIRTUAL_ENV/bin:$PATH"
    export PATH
fi
cd "$SCRIPT_DIR"
python3 ./gateway.py "$@"
