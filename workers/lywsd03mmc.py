
import json
import logger

from contextlib import contextmanager

from mqtt import MqttMessage
from workers.base import BaseWorker

_LOGGER = logger.get(__name__)

REQUIREMENTS = ["bluepy"]


class Lywsd03MmcWorker(BaseWorker):
    def _setup(self):
        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
        for name, mac in self.devices.items():
            _LOGGER.info("Adding %s device '%s' (%s)", repr(self), name, mac)
            self.devices[name] = lywsd03mmc(mac, timeout=self.command_timeout)

    def format_static_topic(self, *args):
        return "/".join([self.topic_prefix, *args])

    def status_update(self):
        for name, lywsd03mmc in self.devices.items():
            ret = lywsd03mmc.readAll()

            if not ret:
                return []

            return [
                MqttMessage(
                    topic=self.format_static_topic(name), payload=json.dumps(ret)
                )
            ]

    def __repr__(self):
        return self.__module__.split(".")[-1]


class lywsd03mmc:

    def __init__(self, mac, timeout=30):
        self.mac = mac
        self.timeout = timeout

        self._temperature = None
        self._humidity = None
        self._battery = None

    @contextmanager
    def connected(self):
        from bluepy import btle

        try:
            _LOGGER.debug("%s connected ", self.mac)
            device = btle.Peripheral()
            device.connect(self.mac)
            device.writeCharacteristic(0x0038, b'\x01\x00', True)
            device.writeCharacteristic(0x0046, b'\xf4\x01\x00', True)
            yield device
            device.disconnect()
        except btle.BTLEDisconnectError as er:
            _LOGGER.debug("failed connect %s", er)
            yield None

    def readAll(self):
        with self.connected() as device:
            if not device:
                return {}

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
            if device.waitForNotifications(self.timeout):
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
        battery =  int.from_bytes(data[3:5], byteorder='little') / 1000

        self._temperature = round(temperature, 1)
        self._humidity = round(humidity)
        self._battery = round(humidity, 4)
