from mqtt import MqttMessage, MqttConfigMessage
from workers.base import BaseWorker

import logger


REQUIREMENTS = ['python-smartgadget']
ATTR_NAMES = [
  ('temperature', 'temperature'),
  ('humidity', 'humidity'),
  ('battery_level', 'battery'),
]
ATTR_CONFIG_MAP = {
  'temperature': {
    'device_class': 'temperature',
    'unit_of_measurement': '°C',
  },
  'humidity': {
    'device_class': 'humidity',
    'unit_of_measurement': '%',
  },
  'battery_level': {
    'device_class': 'battery',
    'unit_of_measurement': '%',
  }
}
_LOGGER = logger.get(__name__)


class SmartgadgetWorker(BaseWorker):
  def _setup(self):
    from sensirionbt import SmartGadget

    _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
    for name, mac in self.devices.items():
      _LOGGER.debug("Adding %s device '%s' (%s)", repr(self), name, mac)
      self.devices[name] = SmartGadget(mac)

  def config(self):
    ret = []
    for name, device in self.devices.items():
      ret.extend(self.config_device(name, device.mac))
    return ret

  def config_device(self, name, mac):
    ret = []
    device = {
      'identifiers': self.format_discovery_id(mac, name),
      'manufacturer': "Sensirion AG",
      'model': "SmartGadget",
      'name': self.format_discovery_name(name),
    }

    for attr, config_name in ATTR_NAMES:
      attr_config = ATTR_CONFIG_MAP[attr]
      payload = {
        'unique_id': self.format_discovery_id(mac, name, config_name),
        'name': self.format_discovery_name(name, config_name),
        'state_topic': self.format_prefixed_topic(name, config_name),
        'device': device,
      }
      payload.update(attr_config)
      ret.append(MqttConfigMessage(MqttConfigMessage.SENSOR,
                                   self.format_discovery_topic(mac, name, config_name),
                                   payload=payload))

    return ret

  def status_update(self):
    from bluepy import btle

    ret = []
    _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))
    for name, device in self.devices.items():
      _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, device.mac)
      try:
        ret.extend(self.update_device_state(name, device))
      except btle.BTLEException as e:
        logger.log_exception(_LOGGER, "Error during update of %s device '%s' (%s): %s", repr(self), name, device.mac, type(e).__name__, suppress=True)
    return ret

  def update_device_state(self, name, device):
    values = device.get_values()

    ret = []
    for attr, config_name in ATTR_NAMES:
      ret.append(MqttMessage(topic=self.format_topic(name, config_name), payload=values[attr]))

    return ret

  def device_for(self, mac):
    from sensirionbt import SmartGadget
    return SmartGadget(mac)
