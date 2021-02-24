import time

from mqtt import MqttMessage

from workers.base import BaseWorker
from utils import booleanize
import logger

REQUIREMENTS = ["bluepy"]
_LOGGER = logger.get(__name__)


class BleDeviceStatus:
    def __init__(
        self,
        worker,
        mac: str,
        name: str,
        available: bool = False,
        last_status_time: float = None,
        message_sent: bool = True,
    ):
        if last_status_time is None:
            last_status_time = time.time()

        self.worker = worker  # type: BlescanmultiWorker
        self.mac = mac.lower()
        self.name = name
        self.available = available
        self.last_status_time = last_status_time
        self.message_sent = message_sent

    def set_status(self, available):
        if available != self.available:
            self.available = available
            self.last_status_time = time.time()
            self.message_sent = False

    def _timeout(self):
        if self.available:
            return self.worker.available_timeout
        else:
            return self.worker.unavailable_timeout

    def has_time_elapsed(self):
        elapsed = time.time() - self.last_status_time
        return elapsed > self._timeout()

    def payload(self):
        if self.available:
            return self.worker.available_payload
        else:
            return self.worker.unavailable_payload

    def generate_messages(self, device):
        messages = []
        if not self.message_sent and self.has_time_elapsed():
            self.message_sent = True
            messages.append(
                MqttMessage(
                    topic=self.worker.format_topic("presence/{}".format(self.name)),
                    payload=self.payload(),
                )
            )
            if self.available:
                messages.append(
                    MqttMessage(
                        topic=self.worker.format_topic(
                            "presence/{}/rssi".format(self.name)
                        ),
                        payload=device.rssi,
                    )
                )
        return messages


class BlescanmultiWorker(BaseWorker):
    # Default values
    devices = {}
    # Payload that should be send when device is available
    available_payload = "home"  # type: str
    # Payload that should be send when device is unavailable
    unavailable_payload = "not_home"  # type: str
    # After what time (in seconds) we should inform that device is available (default: 0 seconds)
    available_timeout = 0  # type: float
    # After what time (in seconds) we should inform that device is unavailable (default: 60 seconds)
    unavailable_timeout = 60  # type: float
    scan_timeout = 10.0  # type: float
    scan_passive = True  # type: str or bool

    def __init__(self, *args, **kwargs):
        from bluepy.btle import Scanner, DefaultDelegate

        class ScanDelegate(DefaultDelegate):
            def __init__(self):
                DefaultDelegate.__init__(self)

            def handleDiscovery(self, dev, isNewDev, isNewData):
                if isNewDev:
                    _LOGGER.debug("Discovered new device: %s" % dev.addr)

        super(BlescanmultiWorker, self).__init__(*args, **kwargs)
        self.scanner = Scanner().withDelegate(ScanDelegate())
        self.last_status = [
            BleDeviceStatus(self, mac, name) for name, mac in self.devices.items()
        ]
        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))

    def status_update(self):
        from bluepy import btle

        _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))

        ret = []

        try:
            devices = self.scanner.scan(
                float(self.scan_timeout), passive=booleanize(self.scan_passive)
            )
            mac_addresses = {device.addr: device for device in devices}

            for status in self.last_status:
                device = mac_addresses.get(status.mac, None)
                status.set_status(device is not None)
                ret += status.generate_messages(device)

        except btle.BTLEException as e:
            logger.log_exception(
                _LOGGER,
                "Error during update (%s)",
                repr(self),
                type(e).__name__,
                suppress=True,
            )

        return ret
