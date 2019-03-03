import logging

from mqtt import MqttMessage

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

  def status_update(self):
    from btlewrap.base import BluetoothBackendException
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
