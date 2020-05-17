import json
import logger

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

    def status_update(self):
        from bluepy import btle

        for name, lywsd02 in self.devices.items():
            try:
                ret = lywsd02.readAll()
            except btle.BTLEDisconnectError as e:
                self.log_connect_exception(_LOGGER, name, e)
            except btle.BTLEException as e:
                self.log_unspecified_exception(_LOGGER, name, e)
            else:
                yield [MqttMessage(topic=self.format_topic(name), payload=json.dumps(ret))]


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
        from bluepy import btle

        _LOGGER.debug("%s connected ", self.mac)
        device = btle.Peripheral()
        device.connect(self.mac)
        yield device
        device.disconnect()

    def readAll(self):
        with self.connected() as device:
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
