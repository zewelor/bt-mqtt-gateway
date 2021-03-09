from const import DEFAULT_PER_DEVICE_TIMEOUT
from exceptions import DeviceTimeoutError
from mqtt import MqttMessage, MqttConfigMessage

from interruptingcow import timeout
from workers.base import BaseWorker, retry
import logger

REQUIREMENTS = [
    # Reference specific commit to include the transitive dependency
    # btlewrap in version 0.0.9. This should be reverted to just
    # "miflora" once miflora version > 0.6 is available on pypi.
    "git+https://github.com/open-homeautomation/miflora.git@ebda66d1f4ba71bc0b98f8383280e59302b40fc8#egg=miflora",
    "bluepy"
]

ATTR_BATTERY = "battery"
ATTR_LOW_BATTERY = 'low_battery'

monitoredAttrs = ["temperature", "moisture", "light", "conductivity", ATTR_BATTERY]
_LOGGER = logger.get(__name__)


class MifloraWorker(BaseWorker):
    per_device_timeout = DEFAULT_PER_DEVICE_TIMEOUT  # type: int

    def _setup(self):
        from miflora.miflora_poller import MiFloraPoller
        from btlewrap.bluepy import BluepyBackend

        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
        for name, mac in self.devices.items():
            _LOGGER.debug("Adding %s device '%s' (%s)", repr(self), name, mac)
            self.devices[name] = {
                "mac": mac,
                "poller": MiFloraPoller(mac, BluepyBackend),
            }

    def config(self, availability_topic):
        ret = []
        for name, data in self.devices.items():
            ret += self.config_device(name, data["mac"])
        return ret

    def config_device(self, name, mac):
        ret = []
        device = {
            "identifiers": [mac, self.format_discovery_id(mac, name)],
            "manufacturer": "Xiaomi",
            "model": "MiFlora",
            "name": self.format_discovery_name(name),
        }

        for attr in monitoredAttrs:
            payload = {
                "unique_id": self.format_discovery_id(mac, name, attr),
                "state_topic": self.format_prefixed_topic(name, attr),
                "name": self.format_discovery_name(name, attr),
                "device": device,
            }

            if attr == "light":
                payload.update(
                    {
                        "unique_id": self.format_discovery_id(mac, name, "illuminance"),
                        "device_class": "illuminance",
                        "unit_of_measurement": "lux",
                    }
                )
            elif attr == "moisture":
                payload.update({"icon": "mdi:water", "unit_of_measurement": "%"})
            elif attr == "conductivity":
                payload.update({"icon": "mdi:leaf", "unit_of_measurement": "µS/cm"})
            elif attr == "temperature":
                payload.update(
                    {"device_class": "temperature", "unit_of_measurement": "°C"}
                )
            elif attr == ATTR_BATTERY:
                payload.update({"device_class": "battery", "unit_of_measurement": "%"})

            ret.append(
                MqttConfigMessage(
                    MqttConfigMessage.SENSOR,
                    self.format_discovery_topic(mac, name, attr),
                    payload=payload,
                )
            )

        ret.append(
            MqttConfigMessage(
                MqttConfigMessage.BINARY_SENSOR,
                self.format_discovery_topic(mac, name, ATTR_LOW_BATTERY),
                payload={
                    "unique_id": self.format_discovery_id(mac, name, ATTR_LOW_BATTERY),
                    "state_topic": self.format_prefixed_topic(name, ATTR_LOW_BATTERY),
                    "name": self.format_discovery_name(name, ATTR_LOW_BATTERY),
                    "device": device,
                    "device_class": "battery",
                },
            )
        )

        return ret

    def status_update(self):
        _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))

        for name, data in self.devices.items():
            _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, data["mac"])
            from btlewrap import BluetoothBackendException

            try:
                with timeout(self.per_device_timeout, exception=DeviceTimeoutError):
                    yield retry(self.update_device_state, retries=self.update_retries, exception_type=BluetoothBackendException)(name, data["poller"])
            except BluetoothBackendException as e:
                logger.log_exception(
                    _LOGGER,
                    "Error during update of %s device '%s' (%s): %s",
                    repr(self),
                    name,
                    data["mac"],
                    type(e).__name__,
                    suppress=True,
                )
            except DeviceTimeoutError:
                logger.log_exception(
                    _LOGGER,
                    "Time out during update of %s device '%s' (%s)",
                    repr(self),
                    name,
                    data["mac"],
                    suppress=True,
                )

    def update_device_state(self, name, poller):
        ret = []
        poller.clear_cache()
        for attr in monitoredAttrs:
            ret.append(
                MqttMessage(
                    topic=self.format_topic(name, attr),
                    payload=poller.parameter_value(attr),
                )
            )

        # Low battery binary sensor
        ret.append(
            MqttMessage(
                topic=self.format_topic(name, ATTR_LOW_BATTERY),
                payload=self.true_false_to_ha_on_off(poller.parameter_value(ATTR_BATTERY) < 10),
            )
        )

        return ret
