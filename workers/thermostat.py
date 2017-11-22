from eq3bt import Thermostat, Mode

readableModes = {
    0: 'off',
    1: 'on',
    2: 'auto',
    3: 'manual',
    4: 'away',
    5: 'boost',
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
          'payload': getattr(thermostat,attr),
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
