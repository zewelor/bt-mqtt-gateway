from mqtt import MqttMessage

from workers.base import BaseWorker, retry
import logger

REQUIREMENTS = ["bluepy"]
_LOGGER = logger.get(__name__)

STATE_ON = "ON"
STATE_OFF = "OFF"
CODES = {
    STATE_ON: "570101",
    STATE_OFF: "570102",
    "PRESS": "570100"
}

SERVICE_UUID = "cba20d00-224d-11e6-9fb8-0002a5d5c51b"
CHARACTERISTIC_UUID = "cba20002-224d-11e6-9fb8-0002a5d5c51b"


class SwitchbotWorker(BaseWorker):
    def _setup(self):

        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
        for name, mac in self.devices.items():
            _LOGGER.info("Adding %s device '%s' (%s)", repr(self), name, mac)
            self.devices[name] = {"bot": None, "state": STATE_OFF, "mac": mac}

    def format_state_topic(self, *args):
        return "/".join([self.state_topic_prefix, *args])

    def status_update(self):

        ret = []
        _LOGGER.debug("Updating %d %s devices", len(self.devices), repr(self))
        for name, bot in self.devices.items():
            _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, bot["mac"])
            ret += self.update_device_state(name, bot["state"])
        return ret

    def on_command(self, topic, value):
        from bluepy.btle import BTLEException

        _, _, device_name, _ = topic.split("/")

        bot = self.devices[device_name]

        switch_func = retry(switch_state, retries=self.command_retries)

        value = value.decode("utf-8")

        _LOGGER.info(
            "Setting %s on %s device '%s' (%s)",
            value,
            repr(self),
            device_name,
            bot["mac"],
        )

        # If status doesn't change, the switchbot shouldn't move
        if bot['state'] == value:
            _LOGGER.debug(
                "Ignoring %s on %s device '%s' with state %s",
                value,
                repr(self),
                device_name,
                bot["state"],
            )
            return []

        try:
            switch_func(bot, value)
        except BTLEException as e:
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

        return self.update_device_state(device_name, value)

    def update_device_state(self, name, value):
        return [MqttMessage(topic=self.format_state_topic(name), payload=value)]


def switch_state(bot, value):
    import binascii
    from bluepy.btle import Peripheral

    bot["bot"] = Peripheral(bot["mac"], "random")
    hand_service = bot["bot"].getServiceByUUID(SERVICE_UUID)
    hand = hand_service.getCharacteristics(CHARACTERISTIC_UUID)[0]
    hand.write(binascii.a2b_hex(CODES[value]))
    bot["bot"].disconnect()
    bot['state'] = STATE_ON if bot['state'] == STATE_OFF else STATE_OFF
