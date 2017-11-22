from config import settings
from mqtt import MqttClient
from workers_manager import WorkersManager

print(settings)

mqtt = MqttClient(settings['mqtt'])

workers = WorkersManager(settings['workers'])
mqtt.publish(workers.get_updates())

# args = settings['workers']['thermostat']['args']
# mqtt.publish(ThermostatWorker(**args).status_update())