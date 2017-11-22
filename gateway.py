from config import settings
from mqtt import MqttClient
from workers.thermostat import ThermostatWorker

print(settings)

mqtt = MqttClient()

args = settings['workers']['thermostat']['args']
mqtt.publish(ThermostatWorker(**args).status_update())