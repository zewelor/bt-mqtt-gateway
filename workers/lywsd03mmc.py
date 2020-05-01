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

    def status_update(self):
        from bluepy import btle

        for name, lywsd03mmc in self.devices.items():
            try:
                ret = lywsd03mmc.readAll()
            except btle.BTLEDisconnectError as e:
                self.log_connect_exception(_LOGGER, name, e)
            except btle.BTLEException as e:
                self.log_unspecified_exception(_LOGGER, name, e)
            else:
                yield [MqttMessage(topic=self.format_topic(name), payload=json.dumps(ret))]


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

        _LOGGER.debug("%s connected ", self.mac)
        device = btle.Peripheral()
        device.connect(self.mac)
        device.writeCharacteristic(0x0038, b'\x01\x00', True)
        device.writeCharacteristic(0x0046, b'\xf4\x01\x00', True)
        yield device

    def readAll(self):
        with self.connected() as device:
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
        battery = int.from_bytes(data[3:5], byteorder='little') / 1000

        self._temperature = round(temperature, 1)
        self._humidity = round(humidity)
        self._battery = round(battery, 4)
