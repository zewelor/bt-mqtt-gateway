from builtins import staticmethod
import logging

from mqtt import MqttMessage, MqttConfigMessage

from workers.base import BaseWorker
import logger

REQUIREMENTS = ['python-eq3bt']
_LOGGER = logger.get(__name__)

STATE_AWAY = 'away'
STATE_ECO  = 'eco'
STATE_HEAT = 'heat'
STATE_AUTO = 'auto'
STATE_MANUAL = 'manual'
STATE_ON = 'on'
STATE_OFF = 'off'

SENSOR_CLIMATE = 'climate'
SENSOR_WINDOW = 'window_open'
SENSOR_BATTERY = 'low_battery'
SENSOR_LOCKED = 'locked'
SENSOR_VALVE = 'valve_state'
SENSOR_TARGET_TEMPERATURE = 'target_temperature'

monitoredAttrs = [SENSOR_BATTERY, SENSOR_VALVE, SENSOR_TARGET_TEMPERATURE, SENSOR_WINDOW, SENSOR_LOCKED]


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
    for name, obj in self.devices.items():
      if isinstance(obj, str):
        self.devices[name] = {"mac": obj, "thermostat": Thermostat(obj)}
      elif isinstance(obj, dict):
        self.devices[name] = {
            "mac": obj["mac"],
            "thermostat": Thermostat(obj["mac"]),
            "discovery_temperature_topic": obj.get("discovery_temperature_topic"),
            "discovery_temperature_template": obj.get("discovery_temperature_template")}
      else:
        raise TypeError("Unsupported configuration format")
      _LOGGER.debug("Adding %s device '%s' (%s)", repr(self), name, self.devices[name]["mac"])
    self._modes_mapper = self.ModesMapper()

  def config(self):
    ret = []
    for name, data in self.devices.items():
      ret += self.config_device(name, data)
    return ret

  def config_device(self, name, data):
    ret = []
    mac = data["mac"]
    device={"identifiers": [mac, self.format_discovery_id(mac, name)],
            "manufacturer": "eQ-3",
            "model": "Smart Radiator Thermostat",
            "name": self.format_discovery_name(name)}

    payload = {"unique_id": self.format_discovery_id(mac, name, SENSOR_CLIMATE),
               "name": self.format_discovery_name(name, SENSOR_CLIMATE),
               "qos": 1,
               "temperature_state_topic": self.format_topic(name, SENSOR_TARGET_TEMPERATURE),
               "temperature_command_topic": self.format_topic(name, SENSOR_TARGET_TEMPERATURE, 'set'),
               "mode_state_topic": self.format_topic(name, 'mode'),
               "mode_command_topic": self.format_topic(name, 'mode', 'set'),
               "away_mode_state_topic": self.format_topic(name, 'away'),
               "away_mode_command_topic": self.format_topic(name, 'away', 'set'),
               "min_temp": 5.0,
               "max_temp": 29.5,
               "temp_step": 0.5,
               "payload_on": "on",
               "payload_off": "off",
               "modes": [STATE_HEAT, STATE_AUTO, STATE_MANUAL, STATE_ECO, STATE_OFF],
               "device": device}
    if data.get("discovery_temperature_topic"):
      payload["current_temperature_topic"] = data["discovery_temperature_topic"]
    if data.get("discovery_temperature_template"):
      payload["current_temperature_template"] = data["discovery_temperature_template"]
    ret.append(MqttConfigMessage(MqttConfigMessage.CLIMATE, self.format_discovery_topic(mac, name, SENSOR_CLIMATE), payload=payload))

    payload = {"unique_id": self.format_discovery_id(mac, name, SENSOR_WINDOW),
               "name": self.format_discovery_name(name, SENSOR_WINDOW),
               "state_topic": self.format_topic(name, SENSOR_WINDOW),
               "device_class": 'window',
               "payload_on": "True",
               "payload_off": "False",
               "device": device}
    ret.append(MqttConfigMessage(MqttConfigMessage.BINARY_SENSOR, self.format_discovery_topic(mac, name, SENSOR_WINDOW), payload=payload))

    payload = {"unique_id": self.format_discovery_id(mac, name, SENSOR_BATTERY),
               "name": self.format_discovery_name(name, SENSOR_BATTERY),
               "state_topic": self.format_topic(name, SENSOR_BATTERY),
               "device_class": 'battery',
               "payload_on": "True",
               "payload_off": "False",
               "device": device}
    ret.append(MqttConfigMessage(MqttConfigMessage.BINARY_SENSOR, self.format_discovery_topic(mac, name, SENSOR_BATTERY), payload=payload))

    payload = {"unique_id": self.format_discovery_id(mac, name, SENSOR_LOCKED),
               "name": self.format_discovery_name(name, SENSOR_LOCKED),
               "state_topic": self.format_topic(name, SENSOR_LOCKED),
               "device_class": 'lock',
               "payload_on": "False",
               "payload_off": "True",
               "device": device}
    ret.append(MqttConfigMessage(MqttConfigMessage.BINARY_SENSOR, self.format_discovery_topic(mac, name, SENSOR_LOCKED),
                                 payload=payload))

    payload = {"unique_id": self.format_discovery_id(mac, name, SENSOR_VALVE),
               "name": self.format_discovery_name(name, SENSOR_VALVE),
               "state_topic": self.format_topic(name, SENSOR_VALVE),
               "unit_of_measurement": "%",
               "device": device}
    ret.append(MqttConfigMessage(MqttConfigMessage.SENSOR, self.format_discovery_topic(mac, name, SENSOR_VALVE), payload=payload))

    return ret


  def status_update(self):
    from bluepy import btle

    ret = []
    _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))
    for name, data in self.devices.items():
      _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, data["mac"])
      try:
        ret += self.update_device_state(name, data["thermostat"])
      except btle.BTLEException as e:
        logger.log_exception(_LOGGER, "Error during update of %s device '%s' (%s): %s", repr(self), name, data["mac"], type(e).__name__, suppress=True)
    return ret

  def on_command(self, topic, value):
    from bluepy import btle
    topic_without_prefix = topic.replace('{}/'.format(self.topic_prefix), '')
    device_name, method, _ = topic_without_prefix.split('/')

    data = self.devices[device_name]

    value = value.decode('utf-8')

    if method == STATE_AWAY:
      method = "mode"
      value = self.ModesMapper.on_off_to_mode(value)

    # It needs to be on separate if because first if can change method
    if method == "mode":
      value = self._modes_mapper.get_reverse_mapping(value)
    elif method == "target_temperature":
      value = float(value)

    _LOGGER.info("Setting %s to %s on %s device '%s' (%s)", method, value, repr(self), device_name, data["mac"])
    try:
      setattr(data["thermostat"], method, value)
    except btle.BTLEException as e:
      logger.log_exception(_LOGGER, "Error setting %s to %s on %s device '%s' (%s): %s", method, value, repr(self), device_name, data["mac"], type(e).__name__)
      return []

    try:
      return self.update_device_state(device_name, data["thermostat"])
    except btle.BTLEException as e:
      logger.log_exception(_LOGGER, "Error during update of %s device '%s' (%s): %s", repr(self), device_name, data["mac"], type(e).__name__, suppress=True)
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
