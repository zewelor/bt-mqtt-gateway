#!/usr/bin/env python3

import sys

from exceptions import WorkerTimeoutError, DeviceTimeoutError

if sys.version_info < (3, 5):
    print("To use this script you need python 3.5 or newer! got %s" % sys.version_info)
    sys.exit(1)

import logger

logger.setup()

import logging
import argparse
import queue

import workers_requirements
from workers_queue import _WORKERS_QUEUE
from mqtt import MqttClient
from workers_manager import WorkersManager


parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument(
    "-d",
    "--debug",
    action="store_true",
    default=False,
    help="Set logging to output debug information",
)
group.add_argument(
    "-q",
    "--quiet",
    action="store_true",
    default=False,
    help="Set logging to just output warnings and errors",
)
parser.add_argument(
    "-s",
    "--suppress-update-failures",
    dest="suppress",
    action="store_true",
    default=False,
    help="Suppress any errors regarding failed device updates",
)
parser.add_argument("-r", "--requirements", type=str, choices=['all', 'configured'],
                    help="Print all or configured only required python libs")
parsed = parser.parse_args()

if parsed.requirements:
    requirements = []
    if parsed.requirements == 'configured':
        requirements = workers_requirements.configured_workers()
    else:
        requirements = workers_requirements.all_workers()

    print(' '.join(requirements))
    exit(0)

from config import settings

_LOGGER = logger.get()
if parsed.quiet:
    _LOGGER.setLevel(logging.WARNING)
elif parsed.debug:
    _LOGGER.setLevel(logging.DEBUG)
    logger.enable_debug_formatter()
else:
    _LOGGER.setLevel(logging.INFO)
logger.suppress_update_failures(parsed.suppress)

_LOGGER.info("Starting")

workers_requirements.verify()

global_topic_prefix = settings["mqtt"].get("topic_prefix")

mqtt = MqttClient(settings["mqtt"])
manager = WorkersManager(settings["manager"], mqtt)
manager.register_workers(global_topic_prefix)
manager.start()

running = True

while running:
    try:
        mqtt.publish(_WORKERS_QUEUE.get(timeout=10).execute())
    except queue.Empty:  # Allow for SIGINT processing
        pass
    except (WorkerTimeoutError, DeviceTimeoutError) as e:
        logger.log_exception(
            _LOGGER,
            str(e) if str(e) else "Timeout while executing worker command",
            suppress=True,
        )
    except (KeyboardInterrupt, SystemExit):
        running = False
        _LOGGER.info(
            "Finish current jobs and shut down. If you need force exit use kill"
        )
    except Exception as e:
        logger.log_exception(
            _LOGGER, "Fatal error while executing worker command: %s", type(e).__name__
        )
        raise e
