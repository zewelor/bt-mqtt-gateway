from eq3bt import Thermostat, Mode

haModesMapping = {
    Mode.Closed: 'off',
    Mode.Open: 'on',
    Mode.Auto: 'auto',
    Mode.Manual: 'manual',
    Mode.Away: 'away',
    Mode.Boost: 'boost',
}

monitoredAttrs = ["low_battery", "valve_state", "target_temperature"]

class ThermostatWorker:
  def __init__(self, devices=None, topic_prefix=None):
    self._devices = devices
    self._topic_prefix = topic_prefix

  def status_update(self):
    ret = []
    for name, mac in self.devices.items():
      thermostat = Thermostat(mac)
      thermostat.update()

      for attr in monitoredAttrs:
        ret.append({
          'topic': self.format_topic(name, attr),
          'payload': getattr(thermostat, attr),
        })

      ret.append({
        'topic': self.format_topic(name, 'mode'),
        'payload': haModesMapping[thermostat.mode],
      })

      ret.append({
        'topic': self.format_topic(name, 'away'),
        'payload': 'ON' if thermostat.mode == Mode.Away else 'OFF'
      })

    return ret

  @property
  def devices(self):
    return self._devices

  @property
  def topic_prefix(self):
    return self._topic_prefix

  def format_topic(self, device, attr):
    return '/'.join([self.topic_prefix, device, attr])
