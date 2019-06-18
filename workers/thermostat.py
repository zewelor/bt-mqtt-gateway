from builtins import staticmethod
import logging

from mqtt import MqttMessage, MqttConfigMessage

from workers.base import BaseWorker
import logger

REQUIREMENTS = ['python-eq3bt']
monitoredAttrs = ["low_battery", "valve_state", "target_temperature", "window_open", "locked"]
_LOGGER = logger.get(__name__)

STATE_AWAY = 'away'
STATE_ECO  = 'eco'
STATE_HEAT = 'heat'
STATE_AUTO = 'auto'
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
        Mode.Auto: STATE_AUTO,
        Mode.Manual: STATE_MANUAL,
        Mode.Away: STATE_ECO,
        Mode.Boost: STATE_HEAT,
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

  def config(self):
    ret = []
    for name, thermostat in self.devices.items():
      ret += self.config_device(name)
    return ret

  def config_device(self, name):
    ret = []
    device={"identifiers": self.format_topic(name, separator="_"),
            "manufacturer": "eQ-3",
            "model": "Smart Radiator Thermostat",
            "name": self.format_topic(name, separator=" ").title()}

    payload = {"unique_id": self.format_topic(name, 'climate', separator="_"),
               "qos": 1,
               "temperature_state_topic": self.format_topic(name, 'target_temperature'),
               "temperature_command_topic": self.format_topic(name, 'target_temperature', 'set'),
               "mode_state_topic": self.format_topic(name, 'mode'),
               "mode_command_topic": self.format_topic(name, 'mode', 'set'),
               "away_mode_state_topic": self.format_topic(name, 'away'),
               "away_command_topic": self.format_topic(name, 'away', 'set'),
               "temp_step": 0.5,
               "payload_on": "'on'",
               "payload_off": "'off'",
               "modes": ["heat", "auto", "manual", "eco", 'off'],
               "device": device}
    ret.append(MqttConfigMessage(MqttConfigMessage.CLIMATE, self.format_topic(name, 'climate', separator="_"), payload=payload))

    payload = {"unique_id": self.format_topic(name, 'window_open', separator="_"),
               "state_topic": self.format_topic(name, 'window_open'),
               "device_class": 'window',
               "device": device}
    ret.append(MqttConfigMessage(MqttConfigMessage.BINARY_SENSOR, self.format_topic(name, 'window_open', separator="_"), payload=payload))

    payload = {"unique_id": self.format_topic(name, 'low_battery', separator="_"),
               "state_topic": self.format_topic(name, 'low_battery'),
               "device_class": 'battery',
               "device": device}
    ret.append(MqttConfigMessage(MqttConfigMessage.BINARY_SENSOR, self.format_topic(name, 'low_battery', separator="_"), payload=payload))

    payload = {"unique_id": self.format_topic(name, 'locked', separator="_"),
               "state_topic": self.format_topic(name, 'locked'),
               "device_class": 'lock',
               "device": device}
    ret.append(MqttConfigMessage(MqttConfigMessage.BINARY_SENSOR, self.format_topic(name, 'locked', separator="_"),
                                 payload=payload))

    payload = {"unique_id": self.format_topic(name, "valve_state", separator="_"),
               "state_topic": self.format_topic(name, "valve_state"),
               "unit_of_measurement": "%",
               "device": device}
    ret.append(MqttConfigMessage(MqttConfigMessage.SENSOR, self.format_topic(name, 'valve_state', separator="_"), payload=payload))

    return ret


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
