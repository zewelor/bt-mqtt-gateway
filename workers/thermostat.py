from builtins import staticmethod
import logging

from mqtt import MqttMessage

from workers.base import BaseWorker
import logger

REQUIREMENTS = ['python-eq3bt']
monitoredAttrs = ["low_battery", "valve_state", "target_temperature", "window_open", "locked"]
_LOGGER = logger.get(__name__)

STATE_AWAY = 'away'
STATE_ECO  = 'eco'
STATE_HEAT = 'heat'
STATE_MANUAL = 'manual'
STATE_ON = 'on'
STATE_OFF = 'off'


class ThermostatWorker(BaseWorker):
  class ModesMapper():
    def __init__(self):
      from eq3bt import Mode

      self._mapped_modes = {
        Mode.Closed: STATE_OFF,
        Mode.Open: STATE_ON,
        Mode.Auto: STATE_HEAT,
        Mode.Manual: STATE_MANUAL,
        Mode.Away: STATE_ECO,
        Mode.Boost: 'boost',
      }

      self._reverse_modes = {v: k for k, v in self._mapped_modes.items()}

    def get_mapping(self, mode):
      if mode < 0:
        return None
      return self._mapped_modes[mode]

    def get_reverse_mapping(self, mode):
      return self._reverse_modes[mode]

    @staticmethod
    def away_mode_on_off(mode):
      if mode == STATE_ECO:
        return STATE_ON
      else:
        return STATE_OFF

    @staticmethod
    def on_off_to_mode(on_off):
      if on_off == STATE_ON:
        return STATE_ECO
      else:
        return STATE_HEAT


  def _setup(self):
    from eq3bt import Thermostat

    _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
    for name, mac in self.devices.items():
      _LOGGER.debug("Adding %s device '%s' (%s)", repr(self), name, mac)
      self.devices[name] = Thermostat(mac)

    self._modes_mapper = self.ModesMapper()

  def status_update(self):
    from bluepy import btle

    ret = []
    _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))
    for name, thermostat in self.devices.items():
      _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, thermostat._conn._mac)
      try:
        ret += self.update_device_state(name, thermostat)
      except btle.BTLEException as e:
        logger.log_exception(_LOGGER, "Error during update of %s device '%s' (%s): %s", repr(self), name, thermostat._conn._mac, type(e).__name__, suppress=True)
    return ret

  def on_command(self, topic, value):
    from bluepy import btle
    _, device_name, method, _ = topic.split('/')

    thermostat = self.devices[device_name]

    value = value.decode('utf-8')

    if method == STATE_AWAY:
      method = "mode"
      value = self.ModesMapper.on_off_to_mode(value)

    # It needs to be on separate if because first if can change method
    if method == "mode":
      value = self._modes_mapper.get_reverse_mapping(value)
    elif method == "target_temperature":
      value = float(value)

    _LOGGER.info("Setting %s to %s on %s device '%s' (%s)", method, value, repr(self), device_name, thermostat._conn._mac)
    try:
      setattr(thermostat, method, value)
    except btle.BTLEException as e:
      logger.log_exception(_LOGGER, "Error setting %s to %s on %s device '%s' (%s): %s", method, value, repr(self), device_name, thermostat._conn._mac, type(e).__name__)
      return []

    try:
      return self.update_device_state(device_name, thermostat)
    except btle.BTLEException as e:
      logger.log_exception(_LOGGER, "Error during update of %s device '%s' (%s): %s", repr(self), device_name, thermostat._conn._mac, type(e).__name__, suppress=True)
      return []

  def update_device_state(self, name, thermostat):
    thermostat.update()

    ret = []
    for attr in monitoredAttrs:
      ret.append(MqttMessage(topic=self.format_topic(name, attr), payload=getattr(thermostat, attr)))

    ha_mode = self._modes_mapper.get_mapping(thermostat.mode)
    ret.append(MqttMessage(topic=self.format_topic(name, 'mode'), payload=ha_mode))
    ret.append(MqttMessage(topic=self.format_topic(name, STATE_AWAY), payload=self.ModesMapper.away_mode_on_off(ha_mode)))

    return ret

  def device_for(self, mac):
    return eq3bt.Thermostat(mac)
