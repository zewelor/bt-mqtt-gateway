from builtins import staticmethod
from mqtt import MqttMessage
from workers.base import BaseWorker

REQUIREMENTS = ['python-eq3bt']

monitoredAttrs = ["low_battery", "valve_state", "target_temperature"]

STATE_BOOST = 'boost'
STATE_AWAY = 'away'
STATE_MANUAL = 'manual'

class ThermostatWorker(BaseWorker):
  class ModesMapper():
    from eq3bt import Mode

    MAPPED_MODES = {
      Mode.Closed: 'off',
      Mode.Open: 'on',
      Mode.Auto: 'auto',
      Mode.Manual: STATE_MANUAL,
      Mode.Away: STATE_AWAY,
      Mode.Boost: STATE_BOOST,
    }

    REVERSED_MODES = {v: k for k, v in MAPPED_MODES.items()}

    @classmethod
    def get_mapping(cls, mode):
      return cls.MAPPED_MODES[mode]

    @classmethod
    def get_reverse_mapping(cls, mode):
      return cls.REVERSED_MODES[mode]

    @staticmethod
    def away_mode_on_off(mode):
      if mode == STATE_AWAY:
        return 'ON'
      else:
        return 'OFF'

    @staticmethod
    def on_off_to_mode(on_off):
      if on_off == 'ON':
        return STATE_AWAY
      else:
        return 'auto'


  def _setup(self):
    from eq3bt import Thermostat

    for name, mac in self.devices.items():
      self.devices[name] = Thermostat(mac)


  def status_update(self):
    ret = []
    for name, thermostat in self.devices.items():
      ret += self.update_device_state(name, thermostat)

    return ret

  def on_command(self, topic, value):
    _, device_name, method = topic.split('/')
    thermostat = self.devices[device_name]

    if method == STATE_AWAY:
      method = "mode"
      value = ModesMapper.on_off_to_mode(value)

    # It needs to be on separate if because first if can change method
    if method == "mode":
      value = ModesMapper.get_reverse_mapping(value)
    elif method == "target_temperature":
      value = float(value)

    setattr(thermostat, method, value)
    return self.update_device_state(device_name, thermostat)

  def update_device_state(self, name, thermostat):
    thermostat.update()

    ret = []
    for attr in monitoredAttrs:
      ret.append(MqttMessage(topic=self.format_topic(name, attr), payload=getattr(thermostat, attr)))

    ret.append(MqttMessage(topic=self.format_topic(name, 'mode'), payload=self.ModesMapper.get_mapping(thermostat.mode)))
    ret.append(MqttMessage(topic=self.format_topic(name, 'away'), payload=self.ModesMapper.away_mode_on_off(thermostat.mode)))

    return ret

  def device_for(self, mac):
    return eq3bt.Thermostat(mac)

  def format_topic(self, device, attr):
    return '/'.join([device, attr])
