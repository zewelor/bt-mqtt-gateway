#!/usr/bin/env python3

import logging
import sys

if sys.version_info < (3, 5):
  print("To use this script you need python 3.5 or newer! got %s" % sys.version_info)
  sys.exit(1)

from logger import _LOGGER
import argparse
from workers_queue import _WORKERS_QUEUE
from config import settings
from mqtt import MqttClient
from workers_manager import WorkersManager

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument('-d', '--debug', action='store_true', default=False)
group.add_argument('-q', '--quiet', action='store_true', default=False)
parsed = parser.parse_args()

if parsed.debug:
  _LOGGER.setLevel(logging.DEBUG)
else:
  _LOGGER.setLevel(logging.INFO)

_LOGGER.debug('Starting')

mqtt = MqttClient(settings['mqtt'])
manager = WorkersManager()
manager.register_workers(settings['manager']).start(mqtt)

running = True

try:
  while running:
      try:
        mqtt.publish(_WORKERS_QUEUE.get(block=True).execute())
      except (KeyboardInterrupt, SystemExit):
        raise
      except Exception as e:
        if not parsed.quiet:
          _LOGGER.exception(e)
except KeyboardInterrupt:
  running = False
  _LOGGER.info('Exiting allowing jobs to finish. If you need force exit use kill')

