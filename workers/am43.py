import json
import time

import logger
from const import DEFAULT_PER_DEVICE_TIMEOUT
from mqtt import MqttMessage, MqttConfigMessage
from workers.base import BaseWorker

_LOGGER = logger.get(__name__)

REQUIREMENTS = [
    "git+https://github.com/GylleTanken/python-zemismart-roller-shade.git"
    "@36738c72d7382e78e1223c8ae569acab10f498e6#egg=Zemismart"
]


class Am43Worker(BaseWorker):
    per_device_timeout = DEFAULT_PER_DEVICE_TIMEOUT  # type: int
    target_range_scale = 3  # type: int
    last_target_position = 255

    def _setup(self):
        self._last_position_by_device = {
            device['mac']: 255 for device in self.devices.values()}
        self._last_device_update = {
            device['mac']: 0 for device in self.devices.values()}

        if not hasattr(self, 'default_update_interval'):
            self.default_update_interval = None

        self.update_interval = self.default_update_interval

        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))

    def config(self, availability_topic):
        ret = []
        for name, data in self.devices.items():
            ret += self.config_device(name, data, availability_topic)
        return ret

    def config_device(self, name, data, availability_topic):
        ret = []
        device = {
            'identifiers': [data['mac'], self.format_discovery_id(data['mac'], name)],
            'manufacturer': 'A-OK',
            'model': 'AM43',
            'name': self.format_discovery_name(name),
        }
        ret.append(
            MqttConfigMessage(
                MqttConfigMessage.COVER,
                self.format_discovery_topic(data['mac'], name, 'shade'),
                payload={
                    'device_class': 'blind',
                    'unique_id': self.format_discovery_id('am43', name, data['mac']),
                    'name': 'Blinds',
                    'availability_topic': "{}/{}".format(self.global_topic_prefix, availability_topic),
                    'device': device,
                    'position_open': 0 + self.target_range_scale,
                    'position_closed': 100 - self.target_range_scale,
                    'set_position_topic': '~/targetPosition/set',
                    'position_topic': '~/currentPosition',
                    'state_topic': '~/positionState',
                    'command_topic': '~/positionState/set',
                    '~': self.format_prefixed_topic(name),
                }
            )
        )
        ret.append(
            MqttConfigMessage(
                MqttConfigMessage.SENSOR,
                self.format_discovery_topic(
                    data['mac'], name, 'shade', 'battery'),
                payload={
                    'device_class': 'battery',
                    'unique_id': self.format_discovery_id('am43', name, data['mac'], 'battery'),
                    'name': 'Battery',
                    'availability_topic': "{}/{}".format(self.global_topic_prefix, availability_topic),
                    '~': self.format_prefixed_topic(name),
                    'unit_of_measurement': '%',
                    'state_topic': '~/battery',
                    'device': device,
                }
            )
        )
        return ret

    # Based on the accessory configuration, this will either
    # return the supplied value right back, or will invert
    # it so 100 is considered open instead of closed
    def correct_value(self, data, value):
        if "invert" in data.keys() and data["invert"]:
            return abs(value - 100)
        else:
            return value

    def get_device_state(self, device_name, data, shade):
        battery = 0
        retry_attempts = 0
        while battery == 0 and retry_attempts < 5:
            # The docs for this library say that sometimes this needs called
            # multiple times, try up to 5 until we get a battery number
            shade.update()

            battery = shade.battery

            if battery > 0:
                if self.last_target_position == 255:
                    # initial unknown value, set to current position
                    #
                    # We don't pass this to correct_value as we want internal state
                    # to agree with the device
                    self.last_target_position = shade.position

                shade_position = self.correct_value(data, shade.position)
                target_position = self.correct_value(
                    data, self.last_target_position)

                previous_position = self._last_position_by_device[data['mac']]
                state = 'stopped'
                if shade_position <= self.target_range_scale:
                    state = 'open'
                elif shade_position >= 100 - self.target_range_scale:
                    state = 'closed'

                if self._last_device_update[data['mac']] - time.time() <= 10 and previous_position != 255:
                    if previous_position < shade_position:
                        state = 'closing'
                    elif previous_position > shade_position:
                        state = 'opening'

                self._last_position_by_device[data['mac']] = shade_position
                self._last_device_update[data['mac']] = time.time()

                return {
                    "currentPosition": shade_position,
                    "targetPosition": target_position,
                    "battery": shade.battery,
                    "positionState": state,
                }
            else:
                _LOGGER.debug("Got battery state 0 for '%s' (%s)",
                              device_name, data["mac"])

    def create_mqtt_messages(self, device_name, device_state):
        return [
            MqttMessage(
                topic=self.format_topic(device_name),
                payload=json.dumps(device_state)
            ),
            MqttMessage(
                topic=self.format_topic(device_name, "currentPosition"),
                payload=device_state["currentPosition"],
                retain=True
            ),
            MqttMessage(
                topic=self.format_topic(device_name, "targetPosition"),
                payload=device_state["targetPosition"]
            ),
            MqttMessage(
                topic=self.format_topic(device_name, "battery"),
                payload=device_state["battery"],
                retain=True
            ),
            MqttMessage(
                topic=self.format_topic(device_name, "positionState"),
                payload=device_state["positionState"]
            )
        ]

    def single_device_status_update(self, device_name, data):
        import Zemismart

        _LOGGER.debug("Updating %s device '%s' (%s)",
                      repr(self), device_name, data["mac"])

        shade = Zemismart.Zemismart(
            data["mac"], data["pin"], max_connect_time=self.per_device_timeout, withMutex=True)
        try:
            with shade:
                ret = []
                device_state = self.get_device_state(device_name, data, shade)
                ret += self.create_mqtt_messages(device_name, device_state)

                if not device_state['positionState'].endswith(
                        'ing') and self.default_update_interval != self.update_interval:
                    ret.append(
                        MqttMessage(
                            topic=self.format_topic('update_interval'),
                            payload=self.default_update_interval
                        )
                    )

                return ret
        except AttributeError as e:
            # This type of error can be thrown from time to time if the underlying
            # zemismart library doesn't connect correctly
            logger.log_exception(
                _LOGGER,
                "Error during update of %s device '%s' (%s): %s",
                repr(self),
                device_name,
                data["mac"],
                type(e).__name__,
                suppress=True,
            )

    def status_update(self):
        _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))

        for device_name, data in self.devices.items():
            yield self.single_device_status_update(device_name, data)

    def on_command(self, topic, value):
        _LOGGER.info("On command called with %s %s", topic, value)
        import Zemismart

        topic_without_prefix = topic.replace(
            "{}/".format(self.topic_prefix), "")
        device_name, field, action = topic_without_prefix.split("/")
        ret = []

        if device_name in self.devices:
            data = self.devices[device_name]
            _LOGGER.debug("On command got device %s %s", device_name, data)
        else:
            logger.log_exception(
                _LOGGER, "Ignore command because device %s is unknown", device_name)
            return ret

        value = value.decode("utf-8")
        if field == "positionState" and action == "set":
            shade = Zemismart.Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout,
                                        withMutex=True)
            try:
                with shade:
                    device_state = self.get_device_state(
                        device_name, data, shade)
                    device_position = self.correct_value(
                        data, device_state["currentPosition"])

                    if value == 'STOP':
                        shade.stop()
                        device_state = {
                            "currentPosition": device_position,
                            "targetPosition": device_position,
                            "battery": shade.battery,
                            "positionState": 'stopped'
                        }
                        self.last_target_position = device_position

                        if self.default_update_interval:
                            ret.append(
                                MqttMessage(
                                    topic=self.format_topic('update_interval'),
                                    payload=self.default_update_interval
                                )
                            )

                        ret += self.create_mqtt_messages(
                            device_name, device_state)
                    elif value == 'OPEN' and device_position > self.target_range_scale:
                        # Yes, for open command we need to call close(), because "closed blinds" in AM43
                        # means that they're hidden, and the window is full open
                        shade.close()
                        device_state = {
                            "currentPosition": device_position,
                            "targetPosition": 0,
                            "battery": shade.battery,
                            "positionState": 'opening'
                        }
                        self.last_target_position = 0

                        if self.default_update_interval:
                            self.update_interval = 3
                            ret.append(
                                MqttMessage(
                                    topic=self.format_topic('update_interval'),
                                    payload=3
                                )
                            )

                        ret += self.create_mqtt_messages(
                            device_name, device_state)
                    elif value == 'CLOSE' and device_position < 100 - self.target_range_scale:
                        # Same as above for 'OPEN': we need to call open() when want to close() the window
                        shade.open()
                        device_state = {
                            "currentPosition": device_position,
                            "targetPosition": 100,
                            "battery": shade.battery,
                            "positionState": 'closing'
                        }
                        self.last_target_position = 100

                        ret += self.create_mqtt_messages(
                            device_name, device_state)

                        if self.default_update_interval:
                            self.update_interval = 3
                            ret.append(
                                MqttMessage(
                                    topic=self.format_topic('update_interval'),
                                    payload=3
                                )
                            )
            except AttributeError as e:
                # This type of error can be thrown from time to time if the underlying
                # zemismart library doesn't connect correctly
                logger.log_exception(
                    _LOGGER,
                    "Error setting %s to %s on %s device '%s' (%s): %s",
                    field,
                    value,
                    repr(self),
                    device_name,
                    data["mac"],
                    type(e).__name__,
                )
        elif field == "targetPosition" and action == "set":
            # internal state of the target position should align with the scale used by the
            # device

            if self.target_range_scale <= int(value) <= 100 - self.target_range_scale:
                value = int((int(value) - self.target_range_scale)
                            * (100 / (100 - self.target_range_scale * 2)))

            target_position = self.correct_value(data, int(value))
            self.last_target_position = target_position

            shade = Zemismart.Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout,
                                        withMutex=True)
            try:
                with shade:
                    # get the current state so we can work out direction for update messages
                    # after getting this, convert so we are using the device scale for
                    # values
                    device_state = self.get_device_state(
                        device_name, data, shade)
                    device_position = self.correct_value(
                        data, device_state["currentPosition"])

                    if device_position == target_position:
                        # no update required, not moved
                        _LOGGER.debug("Position for device '%s' (%s) matches, %s %s",
                                      device_name, data["mac"], device_position, value)
                        return []
                    else:
                        # work out the direction
                        # this compares the values using the caller scale instead
                        # of the internal scale.
                        if device_state["currentPosition"] < int(value):
                            state = "closing"
                        else:
                            state = "opening"

                        # send the new position
                        shade.set_position(target_position)

                        device_state = {
                            "currentPosition": device_position,
                            "targetPosition": target_position,
                            "battery": shade.battery,
                            "positionState": state
                        }

                        ret += self.create_mqtt_messages(
                            device_name, device_state)

                        if self.default_update_interval:
                            self.update_interval = 3
                            ret.append(
                                MqttMessage(
                                    topic=self.format_topic('update_interval'),
                                    payload=3
                                )
                            )
            except AttributeError as e:
                # This type of error can be thrown from time to time if the underlying
                # zemismart library doesn't connect correctly
                logger.log_exception(
                    _LOGGER,
                    "Error setting %s to %s on %s device '%s' (%s): %s",
                    field,
                    value,
                    repr(self),
                    device_name,
                    data["mac"],
                    type(e).__name__,
                )
        elif field == "get" or action == "get":
            ret += self.single_device_status_update(device_name, data)

        return ret
