#!/usr/bin/env python3

import sys

if sys.version_info < (3, 5):
  print("To use this script you need python 3.5 or newer! got %s" % sys.version_info)
  sys.exit(1)

import logger
logger.setup()

import logging
import argparse
import queue

from workers_queue import _WORKERS_QUEUE
from config import settings
from mqtt import MqttClient
from workers_manager import WorkersManager


parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument('-d', '--debug', action='store_true', default=False)
group.add_argument('-q', '--quiet', action='store_true', default=False)
parsed = parser.parse_args()

_LOGGER = logger.get()
if parsed.quiet:
  _LOGGER.setLevel(logging.WARNING)
elif parsed.debug:
  _LOGGER.setLevel(logging.DEBUG)
  logger.enable_debug_formatter()
else:
  _LOGGER.setLevel(logging.INFO)

_LOGGER.debug('Starting')

mqtt = MqttClient(settings['mqtt'])
manager = WorkersManager()
manager.register_workers(settings['manager']).start(mqtt)

running = True

while running:
  try:
    mqtt.publish(_WORKERS_QUEUE.get(timeout=10).execute())
  except queue.Empty: # Allow for SIGINT processing
    pass
  except TimeoutError:
    logger.log_exception(_LOGGER, "Timeout while executing worker command")
  except (KeyboardInterrupt, SystemExit):
    running = False
    _LOGGER.info('Finish current jobs and shut down. If you need force exit use kill')
  except Exception as e:
    logger.log_exception(_LOGGER, "Fatal error while executing worker command: %s", type(e).__name__)
    raise e
