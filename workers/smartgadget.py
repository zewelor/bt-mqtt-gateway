from mqtt import MqttMessage, MqttConfigMessage
from workers.base import BaseWorker

import logger


REQUIREMENTS = ["python-smartgadget"]
ATTR_CONFIG = [
    # (attribute_name, device_class, unit_of_measurement)
    ("temperature", "temperature", "°C"),
    ("humidity", "humidity", "%"),
    ("battery_level", "battery", "%"),
]
_LOGGER = logger.get(__name__)


class SmartgadgetWorker(BaseWorker):
    def _setup(self):
        from sensirionbt import SmartGadget

        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
        for name, mac in self.devices.items():
            _LOGGER.debug("Adding %s device '%s' (%s)", repr(self), name, mac)
            self.devices[name] = SmartGadget(mac)

    def config(self, availability_topic):
        ret = []
        for name, device in self.devices.items():
            ret.extend(self.config_device(name, device.mac))
        return ret

    def config_device(self, name, mac):
        ret = []
        device = {
            "identifiers": self.format_discovery_id(mac, name),
            "manufacturer": "Sensirion AG",
            "model": "SmartGadget",
            "name": self.format_discovery_name(name),
        }

        for attr, device_class, unit in ATTR_CONFIG:
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

        return ret

    def status_update(self):
        from bluepy import btle

        _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))
        for name, device in self.devices.items():
            _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, device.mac)
            try:
                yield self.update_device_state(name, device)
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

    def update_device_state(self, name, device):
        values = device.get_values()

        ret = []
        for attr, device_class, _ in ATTR_CONFIG:
            ret.append(
                MqttMessage(
                    topic=self.format_topic(name, device_class), payload=values[attr]
                )
            )

        return ret
