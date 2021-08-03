import json
import time

import logger
from const import DEFAULT_PER_DEVICE_TIMEOUT
from mqtt import MqttMessage, MqttConfigMessage
from workers.base import BaseWorker, retry

_LOGGER = logger.get(__name__)

REQUIREMENTS = [
    "git+https://github.com/andrey-yantsen/python-zemismart-roller-shade.git"
    "@61a9a38656910e5ff74c45d7e3309eada5edcd01#egg=Zemismart"
]


class Am43Worker(BaseWorker):
    per_device_timeout = DEFAULT_PER_DEVICE_TIMEOUT  # type: int
    target_range_scale = 3  # type: int
    last_target_position = 255

    def _setup(self):
        self._last_position_by_device = {device['mac']: 255 for device in self.devices.values()}
        self._last_device_update = {device['mac']: 0 for device in self.devices.values()}

        if not hasattr(self, 'default_update_interval'):
            self.default_update_interval = None

        if not hasattr(self, 'rapid_update_interval'):
            self.rapid_update_interval = None

        self.update_interval = self.default_update_interval
        self.availability_topic = None

        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))

    def config(self, availability_topic):
        ret = []
        for name, data in self.devices.items():
            ret += self.config_device(name, data, availability_topic)
        return ret

    def _get_hass_device_description(self, name):
        device_class = self.devices[name].get('hass_device_class', 'shade')
        return {
            'identifiers': [self.devices[name]['mac'], self.format_discovery_id(self.devices[name]['mac'], name)],
            'manufacturer': 'A-OK',
            'model': 'AM43',
            'name': '{} ({})'.format(device_class.title(), name),
        }

    def config_device(self, name, data, availability_topic):
        ret = []
        device = self._get_hass_device_description(name)
        ret.append(
            MqttConfigMessage(
                MqttConfigMessage.COVER,
                self.format_discovery_topic(data['mac'], name, 'shade'),
                payload={
                    'device_class': data.get('hass_device_class', 'shade'),
                    'unique_id': self.format_discovery_id('am43', name, data['mac']),
                    'name': 'AM43 Blinds ({})'.format(name),
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
                self.format_discovery_topic(data['mac'], name, 'shade', 'battery'),
                payload={
                    'device_class': 'battery',
                    'unique_id': self.format_discovery_id('am43', name, data['mac'], 'battery'),
                    'name': 'AM43 Blinds ({}) battery'.format(name),
                    'availability_topic': "{}/{}".format(self.global_topic_prefix, availability_topic),
                    '~': self.format_prefixed_topic(name),
                    'unit_of_measurement': '%',
                    'state_topic': '~/battery',
                    'device': device,
                }
            )
        )
        self.availability_topic = "{}/{}".format(self.global_topic_prefix, availability_topic)
        return ret

    def configure_device_timer(self, device_name, timer_id, timer):
        from config import settings

        if not settings.get('manager', {}).get('sensor_config'):
            return

        data = self.devices[device_name]
        device = self._get_hass_device_description(device_name)

        timer_alias = 'timer{}'.format(timer_id)

        if timer is None:
            payload = ''
        else:
            payload = {
                'unique_id': self.format_discovery_id('am43', device_name, data['mac'], timer_alias),
                'name': 'AM43 Blinds ({}) Timer {}: Set to {}% at {}'.format(device_name, timer_id + 1,
                                                                             timer['position'], timer['time']),
                'availability_topic': self.availability_topic,
                'device': device,
                'state_topic': '~/{}'.format(timer_alias),
                'command_topic': '~/{}/set'.format(timer_alias),
                '~': self.format_prefixed_topic(device_name),
            }

        # Creepy way to do HASS sensors not only during the configuration time
        return MqttConfigMessage(
            component=settings['manager']["sensor_config"].get("topic", "homeassistant"),
            name='{}/{}'.format(
                MqttConfigMessage.SWITCH,
                self.format_discovery_topic(data['mac'], device_name, 'shade', timer_alias)
            ),
            payload=payload,
            retain=settings['manager']["sensor_config"].get("retain", True)
        )

    # Based on the accessory configuration, this will either
    # return the supplied value right back, or will invert
    # it so 100 is considered open instead of closed
    def correct_value(self, data, value):
        if "invert" in data.keys() and data["invert"]:
            return abs(value - 100)
        else:
            return value

    def get_device_state(self, device_name, data, shade):
        from Zemismart import Zemismart

        battery = 0
        retry_attempts = 0
        while battery == 0 and retry_attempts < self.update_retries:
            retry_attempts += 1

            # The docs for this library say that sometimes this needs called
            # multiple times, try up to 5 until we get a battery number
            if not shade.update():
                continue

            battery = shade.battery

            if battery > 0:
                if self.last_target_position == 255:
                    # initial unknown value, set to current position
                    #
                    # We don't pass this to correct_value as we want internal state
                    # to agree with the device
                    self.last_target_position = shade.position

                time_from_last_update = time.time() - self._last_device_update[data['mac']]

                shade_position = self.correct_value(data, shade.position)
                target_position = self.correct_value(data, self.last_target_position)

                previous_position = self._last_position_by_device[data['mac']]
                state = 'stopped'
                if shade_position <= self.target_range_scale:
                    state = 'open'
                elif shade_position >= 100 - self.target_range_scale:
                    state = 'closed'

                if self.rapid_update_interval \
                        and time_from_last_update <= self.rapid_update_interval * self.update_retries \
                        and previous_position != 255:
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
                    "time_from_last_update": time_from_last_update,
                    "timers": [
                        {
                            'enabled': timer.enabled,
                            'position': timer.position,
                            'time': '{:02d}:{:02d}'.format(timer.hours, timer.minutes),
                            'repeat': {
                                'Monday': timer.repeats & Zemismart.Timer.REPEAT_MONDAY != 0,
                                'Tuesday': timer.repeats & Zemismart.Timer.REPEAT_TUESDAY != 0,
                                'Wednesday': timer.repeats & Zemismart.Timer.REPEAT_WEDNESDAY != 0,
                                'Thursday': timer.repeats & Zemismart.Timer.REPEAT_THURSDAY != 0,
                                'Friday': timer.repeats & Zemismart.Timer.REPEAT_FRIDAY != 0,
                                'Saturday': timer.repeats & Zemismart.Timer.REPEAT_SATURDAY != 0,
                                'Sunday': timer.repeats & Zemismart.Timer.REPEAT_SUNDAY != 0,
                            }
                        }
                        for timer in shade.timers
                    ],
                }
            else:
                _LOGGER.debug("Got battery state 0 for '%s' (%s)", device_name, data["mac"])

    def create_mqtt_messages(self, device_name, device_state):
        ret = [
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

        for timer_id, timer in enumerate(device_state['timers']):
            hass = self.configure_device_timer(device_name, timer_id, timer)
            if hass:
                ret.append(hass)
            ret.append(
                MqttMessage(
                    topic=self.format_topic(device_name, "timer{}".format(timer_id)),
                    payload='ON' if timer['enabled'] else 'OFF'
                )
            )

        for timer_id in range(len(device_state['timers']), 4):
            hass = self.configure_device_timer(device_name, timer_id, None)
            if hass:
                ret.append(hass)

        return ret

    def single_device_status_update(self, device_name, data):
        _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), device_name, data["mac"])

        from Zemismart import Zemismart
        shade = Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout,
                          withMutex=True, iface=data.get('iface'))
        with shade:
            ret = []
            device_state = self.get_device_state(device_name, data, shade)
            ret += self.create_mqtt_messages(device_name, device_state)

            if self.rapid_update_interval and self.default_update_interval:
                if device_state['positionState'].endswith('ing') and self.default_update_interval == self.update_interval:
                    ret.append(
                        MqttMessage(
                            topic=self.format_topic('update_interval'),
                            payload=self.rapid_update_interval
                        )
                    )
                    self.update_interval = self.rapid_update_interval
                elif not device_state['positionState'].endswith('ing') and self.default_update_interval != self.update_interval:
                    ret.append(
                        MqttMessage(
                            topic=self.format_topic('update_interval'),
                            payload=self.default_update_interval
                        )
                    )
                    self.update_interval = self.default_update_interval

            return ret

    def status_update(self):
        _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))

        for device_name, data in self.devices.items():
            yield retry(self.single_device_status_update, retries=self.update_retries)(device_name, data)

    def set_state(self, state, device_name):
        from Zemismart import Zemismart

        ret = []
        data = self.devices[device_name]
        shade = Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout,
                          withMutex=True, iface=data.get('iface'))
        with shade:
            device_state = self.get_device_state(device_name, data, shade)
            device_position = self.correct_value(data, device_state["currentPosition"])

            if state == 'STOP':
                if not shade.stop():
                    raise AttributeError('shade.stop() failed')

                device_state.update({
                    "currentPosition": device_position,
                    "targetPosition": device_position,
                    "battery": shade.battery,
                    "positionState": 'stopped'
                })
                self.last_target_position = device_position

                if self.default_update_interval and self.rapid_update_interval:
                    self.update_interval = self.default_update_interval
                    ret.append(
                        MqttMessage(
                            topic=self.format_topic('update_interval'),
                            payload=self.default_update_interval
                        )
                    )

                ret += self.create_mqtt_messages(device_name, device_state)
            elif state == 'OPEN' and device_position > self.target_range_scale:
                shade.stop()

                # Yes, for open command we need to call close(), because "closed blinds" in AM43
                # means that they're hidden, and the window is full open
                if not shade.close():
                    raise AttributeError('shade.close() failed')
                device_state.update({
                    "currentPosition": device_position,
                    "targetPosition": 0,
                    "battery": shade.battery,
                    "positionState": 'opening'
                })
                self.last_target_position = 0

                if self.default_update_interval and self.rapid_update_interval:
                    self.update_interval = self.rapid_update_interval
                    ret.append(
                        MqttMessage(
                            topic=self.format_topic('update_interval'),
                            payload=self.rapid_update_interval
                        )
                    )

                ret += self.create_mqtt_messages(device_name, device_state)
            elif state == 'CLOSE' and device_position < 100 - self.target_range_scale:
                shade.stop()

                # Same as above for 'OPEN': we need to call open() when want to close() the window
                if not shade.open():
                    raise AttributeError('shade.open() failed')
                device_state.update({
                    "currentPosition": device_position,
                    "targetPosition": 100,
                    "battery": shade.battery,
                    "positionState": 'closing'
                })
                self.last_target_position = 100

                ret += self.create_mqtt_messages(device_name, device_state)

                if self.default_update_interval and self.rapid_update_interval:
                    self.update_interval = self.rapid_update_interval
                    ret.append(
                        MqttMessage(
                            topic=self.format_topic('update_interval'),
                            payload=self.rapid_update_interval
                        )
                    )
        return ret

    def set_position(self, position, device_name):
        from Zemismart import Zemismart

        ret = []

        # internal state of the target position should align with the scale used by the
        # device
        if self.target_range_scale <= int(position) <= 100 - self.target_range_scale:
            position = int((int(position) - self.target_range_scale) * (100 / (100 - self.target_range_scale * 2)))

        data = self.devices[device_name]
        target_position = self.correct_value(data, int(position))
        self.last_target_position = target_position

        shade = Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout,
                          withMutex=True, iface=data.get('iface'))
        with shade:
            # get the current state so we can work out direction for update messages
            # after getting this, convert so we are using the device scale for
            # values
            device_state = self.get_device_state(device_name, data, shade)
            device_position = self.correct_value(data, device_state["currentPosition"])

            if device_position == target_position:
                # no update required, not moved
                _LOGGER.debug("Position for device '%s' (%s) matches, %s %s",
                              device_name, data["mac"], device_position, position)
                return []
            else:
                # work out the direction
                # this compares the values using the caller scale instead
                # of the internal scale.
                if device_state["currentPosition"] < int(position):
                    state = "closing"
                else:
                    state = "opening"

                # send the new position
                if not shade.set_position(target_position):
                    raise AttributeError('shade.set_position() failed')

                device_state.update({
                    "currentPosition": device_position,
                    "targetPosition": target_position,
                    "battery": shade.battery,
                    "positionState": state
                })

                ret += self.create_mqtt_messages(device_name, device_state)

                if self.default_update_interval and self.rapid_update_interval:
                    self.update_interval = self.rapid_update_interval
                    ret.append(
                        MqttMessage(
                            topic=self.format_topic('update_interval'),
                            payload=self.rapid_update_interval
                        )
                    )
        return ret

    def set_timer_state(self, timer_id, state, device_name):
        from Zemismart import Zemismart

        ret = []

        data = self.devices[device_name]
        target_state = True if state == 'ON' else False

        shade = Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout,
                          withMutex=True, iface=data.get('iface'))
        with shade:
            shade.update()
            shade.timer_toggle(timer_id, target_state)
            device_state = self.get_device_state(device_name, data, shade)
            ret += self.create_mqtt_messages(device_name, device_state)

        return ret

    def handle_mqtt_command(self, topic, value):
        topic_without_prefix = topic.replace("{}/".format(self.topic_prefix), "")
        device_name, field, action = topic_without_prefix.split("/")
        ret = []

        if device_name in self.devices:
            data = self.devices[device_name]
            _LOGGER.debug("On command got device %s %s", device_name, data)
        else:
            _LOGGER.error("Ignore command because device %s is unknown", device_name)
            return ret

        value = value.decode("utf-8")
        if field == "positionState" and action == "set":
            ret += self.set_state(value, device_name)
        elif field == "targetPosition" and action == "set":
            ret += self.set_position(value, device_name)
        elif field.startswith('timer') and action == "set":
            ret += self.set_timer_state(int(field[-1]), value, device_name)
        elif field == "get" or action == "get":
            ret += retry(self.single_device_status_update, retries=self.update_retries)(device_name, data)

        return ret

    def on_command(self, topic, value):
        _LOGGER.info("On command called with %s %s", topic, value)
        return retry(self.handle_mqtt_command, retries=self.command_retries)(topic, value)
