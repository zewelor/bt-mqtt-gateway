import json
import logger

from bluepy import btle
from collections import namedtuple
from contextlib import contextmanager
from struct import unpack

from mqtt import MqttMessage
from workers.base import BaseWorker

_LOGGER = logger.get(__name__)

REQUIREMENTS = ["bluepy"]


class Lywsd02Worker(BaseWorker):
    def _setup(self):
        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
        for name, mac in self.devices.items():
            _LOGGER.info("Adding %s device '%s' (%s)", repr(self), name, mac)
            self.devices[name] = Lywsd02(mac, timeout=self.command_timeout)

    def format_static_topic(self, *args):
        return "/".join([self.topic_prefix, *args])

    def status_update(self):
        for name, lywsd02 in self.devices.items():
            ret = lywsd02.readAll()

            if not ret:
                return []

            return [
                MqttMessage(
                    topic=self.format_static_topic(name), payload=json.dumps(ret)
                )
            ]

    def __repr__(self):
        return self.__module__.split(".")[-1]


class Lywsd02:
    UUID_DATA = "ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6"
    UUID_BATT = "ebe0ccc4-7a0a-4b0c-8a1a-6ff2997da3a6"

    def __init__(self, mac, timeout=30):
        self.mac = mac
        self.timeout = timeout

        self._temperature = None
        self._humidity = None
        self._battery = None

    @contextmanager
    def connected(self):
        try:
            _LOGGER.debug("%s connected ", self.mac)
            device = btle.Peripheral()
            device.connect(self.mac)
            yield device
            device.disconnect()
        except btle.BTLEDisconnectError as er:
            _LOGGER.debug("failed connect %s", er)
            yield None

    def readAll(self):
        with self.connected() as device:
            if not device:
                return {}

            temperature, humidity = self.getData(device)
            battery = self.getBattery(device)
            
            _LOGGER.debug("successfully read %f, %d, %d", temperature, humidity, battery)

            return {
                "temperature": temperature,
                "humidity": humidity,
                "battery": battery,
            }

    def getData(self, device):
        self.subscribe(device, self.UUID_DATA)
        while True:
            if device.waitForNotifications(self.timeout):
                break
        return self._temperature, self._humidity

    def getBattery(self, device):
        c = device.getCharacteristics(uuid=self.UUID_BATT)[0]
        return ord(c.read())

    def subscribe(self, device, uuid):
        device.setDelegate(self)
        c = device.getCharacteristics(uuid=uuid)[0]
        d = c.getDescriptors(forUUID=0x2902)[0]

        d.write(0x01.to_bytes(2, byteorder="little"), withResponse=True)

    def processSensorsData(self, data):
        self._temperature = unpack("H", data[:2])[0] / 100
        self._humidity = data[2]

    def handleNotification(self, handle, data):
        # 0x4b is sensors data
        if handle == 0x4b:
            self.processSensorsData(data)
