from mqtt import MqttMessage, MqttConfigMessage

from workers.base import BaseWorker
import logger

REQUIREMENTS = ['miflora', 'bluepy']
monitoredAttrs = ["temperature", "moisture", "light", "conductivity", "battery"]
_LOGGER = logger.get(__name__)


class MifloraWorker(BaseWorker):
  def _setup(self):
    from miflora.miflora_poller import MiFloraPoller
    from btlewrap.bluepy import BluepyBackend

    _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
    for name, mac in self.devices.items():
      _LOGGER.debug("Adding %s device '%s' (%s)", repr(self), name, mac)
      self.devices[name] = MiFloraPoller(mac, BluepyBackend)

  def config(self):
    ret = []
    for name, poller in self.devices.items():
      ret += self.config_device(name)
    return ret

  def config_device(self, name):
    ret = []
    device={"identifiers": self.format_topic(name, separator="_"),
            "manufacturer": "Xiaomi",
            "model": "MiFlora",
            "name": self.format_topic(name, separator=" ").title()}
    for attr in monitoredAttrs:
      if attr == 'light':
        payload = {"unique_id": self.format_topic(name, 'illuminance', separator="_"),
                   "state_topic": self.format_topic(name, attr),
                   "device_class": 'illuminance',
                   "device": device}
      elif attr == 'moisture':
        payload = {"unique_id": self.format_topic(name, attr, separator="_"),
                   "state_topic": self.format_topic(name, attr),
                   "icon": 'mdi:water',
                   "unit_of_measurement": "%",
                   "device": device}
      elif attr == 'conductivity':
        payload = {"unique_id": self.format_topic(name, attr, separator="_"),
                   "state_topic": self.format_topic(name, attr),
                   "icon": 'mdi:leaf',
                   "unit_of_measurement": "µS/cm",
                   "device": device}
      else:
        payload = {"unique_id": self.format_topic(name, attr, separator="_"),
                   "state_topic": self.format_topic(name, attr),
                   "device_class": attr,
                   "device": device}
      ret.append(MqttConfigMessage(MqttConfigMessage.SENSOR, self.format_topic(name, attr, separator="_"), payload=payload))

    return ret

  def status_update(self):
    _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))
    ret = []
    for name, poller in self.devices.items():
      _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, poller._mac)
      try:
        ret += self.update_device_state(name, poller)
      except BluetoothBackendException as e:
        logger.log_exception(_LOGGER, "Error during update of %s device '%s' (%s): %s", repr(self), name, poller._mac, type(e).__name__, suppress=True)
    return ret

  def update_device_state(self, name, poller):
    ret = []
    poller.clear_cache()
    for attr in monitoredAttrs:
      ret.append(MqttMessage(topic=self.format_topic(name, attr), payload=poller.parameter_value(attr)))
    return ret
