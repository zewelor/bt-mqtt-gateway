from mqtt import MqttMessage

REQUIREMENTS = ['python-eq3bt']

monitoredAttrs = ["low_battery", "valve_state", "target_temperature"]

class ThermostatWorker:
  def __init__(self, devices):
    self._devices = devices

  def status_update(self):
    from eq3bt import Thermostat, Mode

    haModesMapping = {
      Mode.Closed: 'off',
      Mode.Open: 'on',
      Mode.Auto: 'auto',
      Mode.Manual: 'manual',
      Mode.Away: 'away',
      Mode.Boost: 'boost',
    }

    ret = []
    for name, mac in self.devices.items():
      thermostat = Thermostat(mac)
      thermostat.update()

      for attr in monitoredAttrs:
        ret.append(MqttMessage(topic=self.format_topic(name, attr), payload=getattr(thermostat, attr)))

      ret.append(MqttMessage(topic=self.format_topic(name, 'mode'), payload=haModesMapping[thermostat.mode]))
      ret.append(MqttMessage(topic=self.format_topic(name, 'away'), payload='ON' if thermostat.mode == Mode.Away else 'OFF'))

    return ret

  @property
  def devices(self):
    return self._devices

  def format_topic(self, device, attr):
    return '/'.join([device, attr])
