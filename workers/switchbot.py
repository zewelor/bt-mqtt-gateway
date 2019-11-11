from builtins import staticmethod
import logging

from mqtt import MqttMessage

from workers.base import BaseWorker
import logger

REQUIREMENTS = ["bluepy"]
_LOGGER = logger.get(__name__)

STATE_ON = "ON"
STATE_OFF = "OFF"


class SwitchbotWorker(BaseWorker):
    def _setup(self):

        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
        for name, mac in self.devices.items():
            _LOGGER.info("Adding %s device '%s' (%s)", repr(self), name, mac)
            self.devices[name] = {"bot": None, "state": STATE_OFF, "mac": mac}

    def format_state_topic(self, *args):
        return "/".join([self.state_topic_prefix, *args])

    def status_update(self):
        from bluepy import btle

        ret = []
        _LOGGER.debug("Updating %d %s devices", len(self.devices), repr(self))
        for name, bot in self.devices.items():
            _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, bot["mac"])
            try:
                ret += self.update_device_state(name, bot["state"])
            except btle.BTLEException as e:
                logger.log_exception(
                    _LOGGER,
                    "Error during update of %s device '%s' (%s): %s",
                    repr(self),
                    name,
                    bot["mac"],
                    type(e).__name__,
                    suppress=True,
                )
        return ret

    def on_command(self, topic, value):
        from bluepy import btle
        import binascii
        from bluepy.btle import Peripheral

        _, _, device_name, _ = topic.split("/")

        bot = self.devices[device_name]

        value = value.decode("utf-8")

        # It needs to be on separate if because first if can change method

        _LOGGER.debug(
            "Setting %s on %s device '%s' (%s)",
            value,
            repr(self),
            device_name,
            bot["mac"],
        )
        try:
            bot["bot"] = Peripheral(bot["mac"], "random")
            hand_service = bot["bot"].getServiceByUUID(
                "cba20d00-224d-11e6-9fb8-0002a5d5c51b"
            )
            hand = hand_service.getCharacteristics(
                "cba20002-224d-11e6-9fb8-0002a5d5c51b"
            )[0]
            if value == STATE_ON:
                hand.write(binascii.a2b_hex("570101"))
            elif value == STATE_OFF:
                hand.write(binascii.a2b_hex("570102"))
            elif value == "PRESS":
                hand.write(binascii.a2b_hex("570100"))
            bot["bot"].disconnect()
        except btle.BTLEException as e:
            logger.log_exception(
                _LOGGER,
                "Error setting %s on %s device '%s' (%s): %s",
                value,
                repr(self),
                device_name,
                bot["mac"],
                type(e).__name__,
            )
            return []

        try:
            return self.update_device_state(device_name, value)
        except btle.BTLEException as e:
            logger.log_exception(
                _LOGGER,
                "Error during update of %s device '%s' (%s): %s",
                repr(self),
                device_name,
                bot["mac"],
                type(e).__name__,
                suppress=True,
            )
            return []

    def update_device_state(self, name, value):
        return [MqttMessage(topic=self.format_state_topic(name), payload=value)]
