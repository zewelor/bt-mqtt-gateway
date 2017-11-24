from queue import Queue

from apscheduler.schedulers.background import BackgroundScheduler

from config import settings
from mqtt import MqttClient
from workers_manager import WorkersManager

queue = Queue()
scheduler = BackgroundScheduler()
mqtt = MqttClient(settings['mqtt'])
manager = WorkersManager(settings['workers'])

for worker_name, interval in manager.interval_enabled_workers.items():
  queue.put([worker_name])
  scheduler.add_job(lambda x: queue.put([x]), 'interval', seconds=interval, args=[worker_name])

scheduler.start()

while True:
  for worker_name in queue.get(block=True):
    try:
      mqtt.publish(manager.update(worker_name))
    except (KeyboardInterrupt, SystemExit):
      raise
    except:
      print('Some error')
