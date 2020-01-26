import json

from mqtt import MqttMessage

from workers.base import BaseWorker
import logger

REQUIREMENTS = ["bluepy"]
_LOGGER = logger.get(__name__)

BRUSHSTATES = {
    0: "Unknown",
    1: "Initializing",
    2: "Idle",
    3: "Running",
    4: "Charging",
    5: "Setup",
    6: "Flight Menu",
    113: "Final Test",
    114: "PCB Test",
    115: "Sleeping",
    116: "Transport",
}

BRUSHMODES = {
    0: "Off",
    1: "Daily Clean",
    2: "Sensitive",
    3: "Massage",
    4: "Whitening",
    5: "Deep Clean",
    6: "Tongue Cleaning",
    7: "Turbo",
    255: "Unknown",
}

BRUSHSECTORS = {
    0: "Sector 1",
    1: "Sector 2",
    2: "Sector 3",
    3: "Sector 4",
    4: "Sector 5",
    5: "Sector 6",
    7: "Sector 7",
    8: "Sector 8",
    254: "Last sector",
    255: "No sector",
}


class Toothbrush_HomeassistantWorker(BaseWorker):
    def _setup(self):
        self.autoconfCache = {}

    def searchmac(self, devices, mac):
        for dev in devices:
            if dev.addr == mac.lower():
                return dev
        return None

    def get_autoconf_data(self, key, name):
        if key in self.autoconfCache:
            return False
        else:
            self.autoconfCache[key] = True
            return {
                "platform": "mqtt",
                "name": name,
                "state_topic": self.topic_prefix + "/" + key + "/state",
                "availability_topic": self.topic_prefix + "/" + key + "/presence",
                "json_attributes_topic": self.topic_prefix + "/" + key + "/attributes",
                "icon": "mdi:tooth-outline",
            }

    def get_state(self, item):
        if item in BRUSHSTATES:
            return BRUSHSTATES[item]
        else:
            return BRUSHSTATES[0]

    def get_mode(self, item):
        if item in BRUSHMODES:
            return BRUSHMODES[item]
        else:
            return BRUSHMODES[255]

    def get_sector(self, item):
        if item in BRUSHSECTORS:
            return BRUSHSECTORS[item]
        else:
            return BRUSHSECTORS[255]

    def status_update(self):
        from bluepy.btle import Scanner, DefaultDelegate

        class ScanDelegate(DefaultDelegate):
            def __init__(self):
                DefaultDelegate.__init__(self)

            def handleDiscovery(self, dev, isNewDev, isNewData):
                if isNewDev:
                    _LOGGER.debug("Discovered new device: %s" % dev.addr)

        scanner = Scanner().withDelegate(ScanDelegate())
        devices = scanner.scan(5.0)
        ret = []

        for key, item in self.devices.items():
            device = self.searchmac(devices, item["mac"])

            rssi = 0
            presence = 0
            state = 0
            pressure = 0
            time = 0
            mode = 255
            sector = 255

            if device is not None:
                bytes_ = bytearray.fromhex(device.getValueText(255))
                _LOGGER.debug("text: %s" % device.getValueText(255))

                if bytes_[5] > 0:
                    rssi = device.rssi
                    presence = 1
                    state = bytes_[5]
                    pressure = bytes_[6]
                    time = bytes_[7] * 60 + bytes_[8]
                    mode = bytes_[9]
                    sector = bytes_[10]

            attributes = {
                "rssi": rssi,
                "pressure": pressure,
                "time": time,
                "mode": self.get_mode(mode),
                "sector": self.get_sector(sector),
            }
            presence_value = "online" if presence == 1 else "offline"

            ret.append(
                MqttMessage(
                    topic=self.format_topic(key + "/presence"), payload=presence_value
                )
            )
            ret.append(
                MqttMessage(
                    topic=self.format_topic(key + "/state"),
                    payload=self.get_state(state),
                )
            )
            ret.append(
                MqttMessage(
                    topic=self.format_topic(key + "/attributes"),
                    payload=json.dumps(attributes),
                )
            )

            autoconf_data = self.get_autoconf_data(key, item["name"])
            if autoconf_data != False:
                ret.append(
                    MqttMessage(
                        topic=self.autodiscovery_prefix
                        + "/sensor/"
                        + self.topic_prefix
                        + "_"
                        + key
                        + "/config",
                        payload=json.dumps(autoconf_data),
                        retain=True,
                    )
                )

            yield ret
