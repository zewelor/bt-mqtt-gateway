from builtins import staticmethod
import logging

from mqtt import MqttMessage

from workers.base import BaseWorker
import logger

REQUIREMENTS = ["bluepy"]
_LOGGER = logger.get(__name__)

STATE_ON = "ON"
STATE_OFF = "OFF"

# reversed from com.scinan.novolink.lightstring apk
# https://play.google.com/store/apps/details?id=com.scinan.novolink.lightstring

# write characteristics handle
HAND = 0x0025

# hex bytecodes for various operations
HEX_STATE_ON    = "01010101"
HEX_STATE_OFF   = "01010100"
HEX_CONF_PREFIX = "05010203"
HEX_ENUM_STATE  = "000003"
HEX_ENUM_CONF   = "02000000"

class LightstringWorker(BaseWorker):
    def _setup(self):

        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
        for name, mac in self.devices.items():
            _LOGGER.info("Adding %s device '%s' (%s)", repr(self), name, mac)
            self.devices[name] = {"lightstring": None, "state": STATE_OFF, "conf": 0, "mac": mac}

    def format_state_topic(self, *args):
        return "/".join([self.topic_prefix, *args, "state"])

    def format_conf_topic(self, *args):
        return "/".join([self.topic_prefix, *args, "conf"])

    def status_update(self):
        from bluepy import btle
        import binascii
        from bluepy.btle import Peripheral

        class MyDelegate(btle.DefaultDelegate):
            def __init__(self):
                 self.state = ''
                 btle.DefaultDelegate.__init__(self)
            def handleNotification(self, cHandle, data):
                 try:
                     if data[3] in (0, 3):
                         self.state = "OFF"
                     else:
                         self.state = "ON"
                 except:
                     self.state = -1

        class ConfDelegate(btle.DefaultDelegate):
            def __init__(self):
                 self.conf = 0
                 btle.DefaultDelegate.__init__(self)
            def handleNotification(self, cHandle, data):
                 try:
                     self.conf = int(data[17])
                 except:
                     self.conf = -1

        delegate = MyDelegate()
        cdelegate = ConfDelegate()
        ret = []
        _LOGGER.debug("Updating %d %s devices", len(self.devices), repr(self))
        for name, lightstring in self.devices.items():
            _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, lightstring["mac"])
            try:
                lightstring["lightstring"] = Peripheral(lightstring["mac"])
                lightstring["lightstring"].setDelegate(delegate)
                lightstring["lightstring"].writeCharacteristic(HAND, binascii.a2b_hex(HEX_ENUM_STATE))
                lightstring["lightstring"].waitForNotifications(1.0)
                lightstring["lightstring"].disconnect()
                lightstring["lightstring"].connect(lightstring["mac"])
                lightstring["lightstring"].setDelegate(cdelegate)
                lightstring["lightstring"].writeCharacteristic(HAND, binascii.a2b_hex(HEX_ENUM_CONF))
                lightstring["lightstring"].waitForNotifications(1.0)
                lightstring["lightstring"].disconnect()
                if delegate.state != -1:
                    lightstring["state"] = delegate.state
                    ret += self.update_device_state(name, lightstring["state"])
                if cdelegate.conf != -1:
                    lightstring["conf"] = cdelegate.conf
                    ret += self.update_device_conf(name, lightstring["conf"])
            except btle.BTLEException as e:
                logger.log_exception(
                    _LOGGER,
                    "Error during update of %s device '%s' (%s): %s",
                    repr(self),
                    name,
                    lightstring["mac"],
                    type(e).__name__,
                    suppress=True,
                )
        return ret

    def on_command(self, topic, value):
        from bluepy import btle
        import binascii
        from bluepy.btle import Peripheral

        _, _, device_name, _ = topic.split("/")

        lightstring = self.devices[device_name]

        value = value.decode("utf-8")

        # It needs to be on separate if because first if can change method

        _LOGGER.debug(
            "Setting %s on %s device '%s' (%s)",
            value,
            repr(self),
            device_name,
            lightstring["mac"],
        )
        success = False
        while not success:
            try:
                lightstring["lightstring"] = Peripheral(lightstring["mac"])
                if value == STATE_ON:
                    lightstring["lightstring"].writeCharacteristic(HAND, binascii.a2b_hex(HEX_STATE_ON))
                elif value == STATE_OFF:
                    lightstring["lightstring"].writeCharacteristic(HAND, binascii.a2b_hex(HEX_STATE_OFF))
                else:
                    lightstring["lightstring"].writeCharacteristic(HAND, binascii.a2b_hex(HEX_CONF_PREFIX)+bytes([int(value)]))
                lightstring["lightstring"].disconnect()
                success = True
            except btle.BTLEException as e:
                logger.log_exception(
                    _LOGGER,
                    "Error setting %s on %s device '%s' (%s): %s",
                    value,
                    repr(self),
                    device_name,
                    lightstring["mac"],
                    type(e).__name__,
                )
                success = True

        try:
            if value in (STATE_ON, STATE_OFF):
                return self.update_device_state(device_name, value)
            else:
                return self.update_device_conf(device_name, value)
        except btle.BTLEException as e:
            logger.log_exception(
                _LOGGER,
                "Error during update of %s device '%s' (%s): %s",
                repr(self),
                device_name,
                lightstring["mac"],
                type(e).__name__,
                suppress=True,
            )
            return []

    def update_device_state(self, name, value):
        return [MqttMessage(topic=self.format_state_topic(name), payload=value)]

    def update_device_conf(self, name, value):
        return [MqttMessage(topic=self.format_conf_topic(name), payload=value)]
