from mqtt import MqttMessage, MqttConfigMessage

from workers.base import BaseWorker, retry
import logger

REQUIREMENTS = ["python-eq3bt==0.1.11"]
_LOGGER = logger.get(__name__)

STATE_HEAT = "heat"
STATE_AUTO = "auto"
STATE_OFF = "off"

HOLD_NONE = "none"
HOLD_BOOST = "boost"
HOLD_COMFORT = "comfort"
HOLD_ECO = "eco"

SENSOR_CLIMATE = "climate"
SENSOR_WINDOW = "window_open"
SENSOR_BATTERY = "low_battery"
SENSOR_LOCKED = "locked"
SENSOR_VALVE = "valve_state"
SENSOR_AWAY_END = "away_end"
SENSOR_TARGET_TEMPERATURE = "target_temperature"

monitoredAttrs = [
    SENSOR_BATTERY,
    SENSOR_VALVE,
    SENSOR_TARGET_TEMPERATURE,
    SENSOR_WINDOW,
    SENSOR_LOCKED,
]


class ThermostatWorker(BaseWorker):
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
                    "discovery_temperature_topic": obj.get(
                        "discovery_temperature_topic"
                    ),
                    "discovery_temperature_template": obj.get(
                        "discovery_temperature_template"
                    ),
                }
            else:
                raise TypeError("Unsupported configuration format")
            _LOGGER.debug(
                "Adding %s device '%s' (%s)",
                repr(self),
                name,
                self.devices[name]["mac"],
            )

    def config(self, availability_topic):
        ret = []
        for name, data in self.devices.items():
            ret += self.config_device(name, data, availability_topic)
        return ret

    def config_device(self, name, data, availability_topic):
        ret = []
        mac = data["mac"]
        device = {
            "identifiers": [mac, self.format_discovery_id(mac, name)],
            "manufacturer": "eQ-3",
            "model": "Smart Radiator Thermostat",
            "name": self.format_discovery_name(name),
        }

        payload = {
            "unique_id": self.format_discovery_id(mac, name, SENSOR_CLIMATE),
            "name": self.format_discovery_name(name, SENSOR_CLIMATE),
            "qos": 1,
            "availability_topic": availability_topic,
            "temperature_state_topic": self.format_prefixed_topic(
                name, SENSOR_TARGET_TEMPERATURE
            ),
            "temperature_command_topic": self.format_prefixed_topic(
                name, SENSOR_TARGET_TEMPERATURE, "set"
            ),
            "mode_state_topic": self.format_prefixed_topic(name, "mode"),
            "mode_command_topic": self.format_prefixed_topic(name, "mode", "set"),
            "away_mode_state_topic": self.format_prefixed_topic(name, "away"),
            "away_mode_command_topic": self.format_prefixed_topic(name, "away", "set"),
            "hold_state_topic": self.format_prefixed_topic(name, "hold"),
            "hold_command_topic": self.format_prefixed_topic(name, "hold", "set"),
            "json_attributes_topic": self.format_prefixed_topic(
                name, "json_attributes"
            ),
            "min_temp": 5.0,
            "max_temp": 29.5,
            "temp_step": 0.5,
            "modes": [STATE_HEAT, STATE_AUTO, STATE_OFF],
            "hold_modes": [HOLD_BOOST, HOLD_COMFORT, HOLD_ECO],
            "device": device,
        }
        if data.get("discovery_temperature_topic"):
            payload["current_temperature_topic"] = data["discovery_temperature_topic"]
        if data.get("discovery_temperature_template"):
            payload["current_temperature_template"] = data[
                "discovery_temperature_template"
            ]
        ret.append(
            MqttConfigMessage(
                MqttConfigMessage.CLIMATE,
                self.format_discovery_topic(mac, name, SENSOR_CLIMATE),
                payload=payload,
            )
        )

        payload = {
            "unique_id": self.format_discovery_id(mac, name, SENSOR_WINDOW),
            "name": self.format_discovery_name(name, SENSOR_WINDOW),
            "state_topic": self.format_prefixed_topic(name, SENSOR_WINDOW),
            "availability_topic": availability_topic,
            "device_class": "window",
            "payload_on": "true",
            "payload_off": "false",
            "device": device,
        }
        ret.append(
            MqttConfigMessage(
                MqttConfigMessage.BINARY_SENSOR,
                self.format_discovery_topic(mac, name, SENSOR_WINDOW),
                payload=payload,
            )
        )

        payload = {
            "unique_id": self.format_discovery_id(mac, name, SENSOR_BATTERY),
            "name": self.format_discovery_name(name, SENSOR_BATTERY),
            "state_topic": self.format_prefixed_topic(name, SENSOR_BATTERY),
            "availability_topic": availability_topic,
            "device_class": "battery",
            "payload_on": "true",
            "payload_off": "false",
            "device": device,
        }
        ret.append(
            MqttConfigMessage(
                MqttConfigMessage.BINARY_SENSOR,
                self.format_discovery_topic(mac, name, SENSOR_BATTERY),
                payload=payload,
            )
        )

        payload = {
            "unique_id": self.format_discovery_id(mac, name, SENSOR_LOCKED),
            "name": self.format_discovery_name(name, SENSOR_LOCKED),
            "state_topic": self.format_prefixed_topic(name, SENSOR_LOCKED),
            "availability_topic": availability_topic,
            "device_class": "lock",
            "payload_on": "false",
            "payload_off": "true",
            "device": device,
        }
        ret.append(
            MqttConfigMessage(
                MqttConfigMessage.BINARY_SENSOR,
                self.format_discovery_topic(mac, name, SENSOR_LOCKED),
                payload=payload,
            )
        )

        payload = {
            "unique_id": self.format_discovery_id(mac, name, SENSOR_VALVE),
            "name": self.format_discovery_name(name, SENSOR_VALVE),
            "state_topic": self.format_prefixed_topic(name, SENSOR_VALVE),
            "availability_topic": availability_topic,
            "unit_of_measurement": "%",
            "device": device,
        }
        ret.append(
            MqttConfigMessage(
                MqttConfigMessage.SENSOR,
                self.format_discovery_topic(mac, name, SENSOR_VALVE),
                payload=payload,
            )
        )

        return ret

    def status_update(self):
        from bluepy import btle

        _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))
        for name, data in self.devices.items():
            _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, data["mac"])
            thermostat = data["thermostat"]
            try:
                retry(thermostat.update, retries=self.update_retries, exception_type=btle.BTLEException)()
            except btle.BTLEException as e:
                logger.log_exception(
                    _LOGGER,
                    "Error during update of %s device '%s' (%s): %s",
                    repr(self),
                    name,
                    data["mac"],
                    type(e).__name__,
                    suppress=True,
                )
            else:
                yield retry(self.present_device_state, retries=self.update_retries, exception_type=btle.BTLEException)(name, thermostat)

    def on_command(self, topic, value):
        from bluepy import btle
        from eq3bt import Mode

        default_fallback_mode = Mode.Auto

        topic_without_prefix = topic.replace("{}/".format(self.topic_prefix), "")
        device_name, method, _ = topic_without_prefix.split("/")

        if device_name in self.devices:
            data = self.devices[device_name]
            thermostat = data["thermostat"]
        else:
            logger.log_exception(_LOGGER, "Ignore command because device %s is unknown", device_name)
            return []

        value = value.decode("utf-8")
        if method == "mode":
            state_mapping = {
                STATE_HEAT: Mode.Manual,
                STATE_AUTO: Mode.Auto,
                STATE_OFF: Mode.Closed,
            }
            if value in state_mapping:
                value = state_mapping[value]
            else:
                logger.log_exception(_LOGGER, "Invalid mode setting %s", value)
                return []

        elif method == "hold":
            if value == HOLD_BOOST:
                method = "mode"
                value = Mode.Boost
            elif value in (HOLD_COMFORT, HOLD_ECO):
                method = "preset"
            elif value == "off":
                method = "mode"
                value = default_fallback_mode
            else:
                logger.log_exception(_LOGGER, "Invalid hold setting %s", value)
                return []

        elif method == "away":
            method = "mode"
            if value == 'OFF':
                value = default_fallback_mode
            else:
                value = Mode.Away
        elif method == "target_temperature":
            value = float(value)

        _LOGGER.info(
            "Setting %s to %s on %s device '%s' (%s)",
            method,
            value,
            repr(self),
            device_name,
            data["mac"],
        )
        try:
            if method == "preset":
                if value == HOLD_COMFORT:
                    retry(thermostat.activate_comfort, retries=self.command_retries, exception_type=btle.BTLEException)()
                else:
                    retry(thermostat.activate_eco, retries=self.command_retries, exception_type=btle.BTLEException)()
            else:
                retry(setattr, retries=self.command_retries, exception_type=btle.BTLEException)(thermostat, method, value)
        except btle.BTLEException as e:
            logger.log_exception(
                _LOGGER,
                "Error setting %s to %s on %s device '%s' (%s): %s",
                method,
                value,
                repr(self),
                device_name,
                data["mac"],
                type(e).__name__,
            )
            return []

        return retry(self.present_device_state, retries=self.command_retries, exception_type=btle.BTLEException)(device_name, thermostat)

    def present_device_state(self, name, thermostat):
        from eq3bt import Mode

        ret = []
        attributes = {}
        for attr in monitoredAttrs:
            value = getattr(thermostat, attr)
            ret.append(MqttMessage(topic=self.format_topic(name, attr), payload=value))

            if attr != SENSOR_TARGET_TEMPERATURE:
                attributes[attr] = value

        if thermostat.away_end:
            attributes[SENSOR_AWAY_END] = thermostat.away_end.isoformat()
        else:
            attributes[SENSOR_AWAY_END] = None

        ret.append(
            MqttMessage(
                topic=self.format_topic(name, "json_attributes"), payload=attributes
            )
        )

        mapping = {
            Mode.Auto: STATE_AUTO,
            Mode.Closed: STATE_OFF,
            Mode.Boost: STATE_AUTO,
        }
        mode = mapping.get(thermostat.mode, STATE_HEAT)

        if thermostat.mode == Mode.Boost:
            hold = HOLD_BOOST
        elif thermostat.mode == Mode.Away:
            hold = "off"
        elif thermostat.target_temperature == thermostat.comfort_temperature:
            hold = HOLD_COMFORT
        elif thermostat.target_temperature == thermostat.eco_temperature:
            hold = HOLD_ECO
        else:
            hold = HOLD_NONE

        ret.append(MqttMessage(topic=self.format_topic(name, "mode"), payload=mode))
        ret.append(MqttMessage(topic=self.format_topic(name, "hold"), payload=hold))
        ret.append(
            MqttMessage(
                topic=self.format_topic(name, "away"),
                payload=self.true_false_to_ha_on_off(thermostat.mode == Mode.Away),
            )
        )

        return ret
