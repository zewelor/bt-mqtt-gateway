from config import settings
from mqtt import MqttClient
from workers_manager import WorkersManager

mqtt = MqttClient(settings['mqtt'])

manager = WorkersManager(settings['workers'])
for worker_name in manager.workers.keys():
  mqtt.publish(manager.update(worker_name))
