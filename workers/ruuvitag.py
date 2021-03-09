from mqtt import MqttMessage, MqttConfigMessage
from workers.base import BaseWorker

import logger


REQUIREMENTS = ["ruuvitag_sensor"]

# Supports all attributes of Data Format 2, 3, 4 and 5 of the RuuviTag.
# See https://github.com/ruuvi/ruuvi-sensor-protocols for the sensor protocols.
# Available attributes:
# +-----------------------------+---+---+---+---+
# | Attribute / Data Format     | 2 | 3 | 4 | 5 |
# +-----------------------------+---+---+---+---+
# | acceleration                |   | X |   | X |
# | acceleration_x              |   | X |   | X |
# | acceleration_y              |   | X |   | X |
# | acceleration_z              |   | X |   | X |
# | battery                     |   | X |   | X |
# | data_format                 | X | X | X | X |
# | humidity                    | X | X | X | X |
# | identifier                  |   |   | X |   |
# | low_battery                 |   | X |   | X |
# | mac                         |   |   |   | X |
# | measurement_sequence_number |   |   |   | X |
# | movement_counter            |   |   |   | X |
# | pressure                    | X | X | X | X |
# | temperature                 | X | X | X | X |
# | tx_power                    |   |   |   | X |
# +-----------------------------+---+---+---+---+
ATTR_CONFIG = [
    # (attribute_name, device_class, unit_of_measurement)
    ("acceleration", "none", "mG"),
    ("acceleration_x", "none", "mG"),
    ("acceleration_y", "none", "mG"),
    ("acceleration_z", "none", "mG"),
    ("battery", "battery", "mV"),
    ("data_format", "none", ""),
    ("humidity", "humidity", "%"),
    ("identifier", "none", ""),
    ("mac", "none", ""),
    ("measurement_sequence_number", "none", ""),
    ("movement_counter", "none", ""),
    ("pressure", "pressure", "hPa"),
    ("temperature", "temperature", "°C"),
    ("tx_power", "none", "dBm"),
]
ATTR_LOW_BATTERY = "low_battery"
# "[Y]ou should plan to replace the battery when the voltage drops below 2.5 volts"
# Source: https://github.com/ruuvi/ruuvitag_fw/wiki/FAQ:-battery
LOW_BATTERY_VOLTAGE = 2500
_LOGGER = logger.get(__name__)


class RuuvitagWorker(BaseWorker):
    def _setup(self):
        from ruuvitag_sensor.ruuvitag import RuuviTag

        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
        for name, mac in self.devices.items():
            _LOGGER.debug("Adding %s device '%s' (%s)", repr(self), name, mac)
            self.devices[name] = RuuviTag(mac)

    def config(self, availability_topic):
        ret = []
        for name, device in self.devices.items():
            ret.extend(self.config_device(name, device.mac))
        return ret

    def config_device(self, name, mac):
        ret = []
        device = {
            "identifiers": self.format_discovery_id(mac, name),
            "manufacturer": "Ruuvi",
            "model": "RuuviTag",
            "name": self.format_discovery_name(name),
        }

        for _, device_class, unit in ATTR_CONFIG:
            payload = {
                "unique_id": self.format_discovery_id(mac, name, device_class),
                "name": self.format_discovery_name(name, device_class),
                "state_topic": self.format_prefixed_topic(name, device_class),
                "device": device,
                "device_class": device_class,
                "unit_of_measurement": unit,
            }
            ret.append(
                MqttConfigMessage(
                    MqttConfigMessage.SENSOR,
                    self.format_discovery_topic(mac, name, device_class),
                    payload=payload,
                )
            )

        # Add low battery config
        ret.append(
            MqttConfigMessage(
                MqttConfigMessage.BINARY_SENSOR,
                self.format_discovery_topic(mac, name, ATTR_LOW_BATTERY),
                payload={
                    "unique_id": self.format_discovery_id(mac, name, ATTR_LOW_BATTERY),
                    "name": self.format_discovery_name(name, ATTR_LOW_BATTERY),
                    "state_topic": self.format_prefixed_topic(name, ATTR_LOW_BATTERY),
                    "device": device,
                    "device_class": "battery",
                },
            )
        )

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
                logger.log_exception(
                    _LOGGER,
                    "Error during update of %s device '%s' (%s): %s",
                    repr(self),
                    name,
                    device.mac,
                    type(e).__name__,
                    suppress=True,
                )
        return ret

    def update_device_state(self, name, device):
        values = device.update()

        ret = []
        for attr, device_class, _ in ATTR_CONFIG:
            try:
                ret.append(
                    MqttMessage(
                        topic=self.format_topic(name, device_class),
                        payload=values[attr],
                    )
                )
            except KeyError:
                # The data format of this sensor doesn't have this attribute, so ignore it.
                pass

        # Low battery binary sensor
        #
        try:
            ret.append(
                MqttMessage(
                    topic=self.format_topic(name, ATTR_LOW_BATTERY),
                    payload=self.true_false_to_ha_on_off(
                        values["battery"] < LOW_BATTERY_VOLTAGE
                    ),
                )
            )
        except KeyError:
            # The data format of this sensor doesn't have the battery attribute, so ignore it.
            pass

        return ret
