from exceptions import DeviceTimeoutError
from mqtt import MqttMessage, MqttConfigMessage

from interruptingcow import timeout
from workers.base import BaseWorker
import logger
import json
import time
from contextlib import contextmanager

REQUIREMENTS = ["bluepy"]

ATTR_BATTERY = "battery"
ATTR_LOW_BATTERY = 'low_battery'

monitoredAttrs = ["temperature", "humidity", ATTR_BATTERY]
_LOGGER = logger.get(__name__)

class Lywsd03Mmc_HomeassistantWorker(BaseWorker):
    """
    This worker for the Lywsd03Mmc creates the sensor entries in
    MQTT for Home Assistant. It also creates a binary sensor for
    low batteries. It supports connection retries.
    """
    def _setup(self):
        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
        for name, mac in self.devices.items():
            _LOGGER.debug("Adding %s device '%s' (%s)", repr(self), name, mac)
            self.devices[name] = {
                "mac": mac,
                "poller": Lywsd03Mmc2Poller(mac),
            }

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
            "model": "Mijia Lywsd03Mmc",
            "name": self.format_discovery_name(name),
        }

        for attr in monitoredAttrs:
            payload = {
                "unique_id": self.format_discovery_id(mac, name, attr),
                "state_topic": self.format_prefixed_topic(name, attr),
                "name": self.format_discovery_name(name, attr),
                "device": device,
            }

            if attr == "humidity":
                payload.update({"icon": "mdi:water", "unit_of_measurement": "%"})
            elif attr == "temperature":
                payload.update(
                    {"device_class": "temperature", "unit_of_measurement": "°C"}
                )
            elif attr == ATTR_BATTERY:
                payload.update({"device_class": "battery", "unit_of_measurement": "V"})

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
        from bluepy import btle
        _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))

        for name, data in self.devices.items():
            _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, data["mac"])
            # from btlewrap import BluetoothBackendException

            try:
                with timeout(self.command_timeout, exception=DeviceTimeoutError):
                    yield self.update_device_state(name, data["poller"])
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
        if poller.readAll() is None :
            return ret
        for attr in monitoredAttrs:

            attrValue = None
            if attr == "humidity":
                attrValue = poller.getHumidity()
            elif attr == "temperature":
                attrValue = poller.getTemperature()
            elif attr == ATTR_BATTERY:
                attrValue = poller.getBattery()

            ret.append(
                MqttMessage(
                    topic=self.format_topic(name, attr),
                    payload=attrValue,
                )
            )

        # Low battery binary sensor
        ret.append(
            MqttMessage(
                topic=self.format_topic(name, ATTR_LOW_BATTERY),
                payload=self.true_false_to_ha_on_off(poller.getBattery() < 3),
            )
        )

        return ret

class Lywsd03Mmc2Poller:

    def __init__(self, mac, maxattempt=4):
        self.mac = mac
        self.maxattempt = maxattempt

        self._temperature = None
        self._humidity = None
        self._battery = None

    @contextmanager
    def connected(self):
        from bluepy import btle

        attempt = 1
        while attempt < (self.maxattempt + 1) :
            try:
                device = btle.Peripheral()
                _LOGGER.debug("trying to connect to %s", self.mac)
                device.connect(self.mac)
                _LOGGER.debug("connected to %s", self.mac)
                device.writeCharacteristic(0x0038, b'\x01\x00', True)
                device.writeCharacteristic(0x0046, b'\xf4\x01\x00', True)
                _LOGGER.debug("%s query done ", self.mac)
                yield device
                device.disconnect()
                _LOGGER.debug("%s is disconnected ", self.mac)
                attempt = (self.maxattempt + 1)
            except btle.BTLEException as er:
                _LOGGER.debug("failed to connect to %s : " + str(attempt) + "/" + str(self.maxattempt) + " attempt", self.mac)
                if attempt == self.maxattempt :
                    yield None
                    pass
                    return
                else:
                    attempt = attempt + 1
                    _LOGGER.debug("waiting for next try...")
                    time.sleep(1)
                    pass

    def readAll(self):
        with self.connected() as device:
            if device is None :
                return None

            self.getData(device)
            temperature = self.getTemperature()
            humidity = self.getHumidity()
            battery = self.getBattery()

            _LOGGER.debug("successfully read %f, %d, %d", temperature, humidity, battery)

            return {
                "temperature": temperature,
                "humidity": humidity,
                "battery": battery,
            }

    def getData(self, device):
        self.subscribe(device)
        while True:
            if device.waitForNotifications(1):
                break
        return self._temperature, self._humidity, self._battery

    def getTemperature(self):
        return self._temperature;

    def getHumidity(self):
        return self._humidity;

    def getBattery(self):
        return self._battery;

    def subscribe(self, device):
        device.setDelegate(self)

    def handleNotification(self, handle, data):
        temperature = int.from_bytes(data[0:2], byteorder='little', signed=True) / 100
        humidity = int.from_bytes(data[2:3], byteorder='little')
        battery = int.from_bytes(data[3:5], byteorder='little') / 1000

        self._temperature = round(temperature, 1)
        self._humidity = round(humidity)
        self._battery = round(battery, 4)
