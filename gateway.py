import logging
import sys
if sys.version_info < (3,4):
  print("To use this script you need python 3.4 or newer! got %s" % sys.version_info)
  sys.exit(1)

from logger import _LOGGER
import argparse
from queue import Queue
from config import settings
from mqtt import MqttClient
from workers_manager import WorkersManager
from apscheduler.schedulers.background import BackgroundScheduler

parser = argparse.ArgumentParser()
parser.add_argument('-d', '--debug', action='store_true', default=False)
parsed = parser.parse_args()

if parsed.debug:
  _LOGGER.setLevel(logging.DEBUG)
else:
  _LOGGER.setLevel(logging.INFO)

queue = Queue()
scheduler = BackgroundScheduler()
mqtt = MqttClient(settings['mqtt'])
manager = WorkersManager(settings['workers'])

_LOGGER.info('Starting')

for worker_name, interval in manager.interval_enabled_workers.items():
  _LOGGER.debug("Added: %s with %d seconds interval" % (worker_name, interval))
  queue.put([worker_name])
  scheduler.add_job(lambda x: queue.put([x]), 'interval', seconds=interval, args=[worker_name])

scheduler.start()

running = True

try:
  while running:
    for worker_name in queue.get(block=True):
      try:
        mqtt.publish(manager.update(worker_name))
      except (KeyboardInterrupt, SystemExit):
        raise
      except:
        _LOGGER.info('Some error')
except KeyboardInterrupt:
  running = False
  _LOGGER.info('Exiting allowing jobs to finish. If you need force exit use kill')
