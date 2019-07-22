import logging

from mqtt import MqttMessage, MqttConfigMessage

from workers.base import BaseWorker
import logger

REQUIREMENTS = ['mithermometer', 'bluepy']
monitoredAttrs = ["temperature", "humidity", "battery"]
_LOGGER = logger.get(__name__)


class MithermometerWorker(BaseWorker):
  def _setup(self):
    from mithermometer.mithermometer_poller import MiThermometerPoller
    from btlewrap.bluepy import BluepyBackend

    _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
    for name, mac in self.devices.items():
      _LOGGER.debug("Adding %s device '%s' (%s)", repr(self), name, mac)
      self.devices[name] = {"mac":mac, "poller": MiThermometerPoller(mac, BluepyBackend)}

  def config(self):
    ret = []
    for name, data in self.devices.items():
      ret += self.config_device(name, data["mac"])
    return ret

  def config_device(self, name, mac):
    ret = []
    device = {
      "identifiers": [mac, self.format_discovery_id(mac, name)],
      "manufacturer": "Xiaomi",
      "model": "LYWSD(CGQ/01ZM)",
      "name": self.format_discovery_name(name)
    }

    for attr in monitoredAttrs:
      payload = {
        "unique_id": self.format_discovery_id(mac, name, attr),
        "name": self.format_discovery_name(name, attr),
        "state_topic": self.format_topic(name, attr),
        "device_class": attr,
        "device": device
      }

      if attr == 'temperature':
        payload["unit_of_measurement"] = "°C"
      elif attr == 'humidity':
        payload["unit_of_measurement"] = "%"
      elif attr == 'battery':
        payload["unit_of_measurement"] = "%"

      ret.append(MqttConfigMessage(MqttConfigMessage.SENSOR, self.format_discovery_topic(mac, name, attr), payload=payload))

    return ret

  def status_update(self):
    _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))
    ret = []
    for name, data in self.devices.items():
      _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, data["mac"])
      from btlewrap import BluetoothBackendException
      try:
        ret += self.update_device_state(name, data["poller"])
      except BluetoothBackendException as e:
        logger.log_exception(_LOGGER, "Error during update of %s device '%s' (%s): %s", repr(self), name, data["mac"], type(e).__name__, suppress=True)
    return ret

  def update_device_state(self, name, poller):
    ret = []
    poller.clear_cache()
    for attr in monitoredAttrs:
      ret.append(MqttMessage(topic=self.format_topic(name, attr), payload=poller.parameter_value(attr)))
    return ret
