from const import DEFAULT_PER_DEVICE_TIMEOUT

import json
import logger
import time
from mqtt import MqttMessage
from workers.base import BaseWorker

_LOGGER = logger.get(__name__)

REQUIREMENTS = [
    "git+https://github.com/GylleTanken/python-zemismart-roller-shade.git@36738c72d7382e78e1223c8ae569acab10f498e6#egg=Zemismart"
]

class Am43Worker(BaseWorker):

    per_device_timeout = DEFAULT_PER_DEVICE_TIMEOUT  # type: int
    last_target_position = 255

    def _setup(self):
        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))

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
                    self.last_target_position = shade.position

                return {
                    "currentPosition": shade.position,
                    "targetPosition": self.last_target_position,
                    "battery": shade.battery,
                    "positionState": "STOPPED"
                }
            else:
                _LOGGER.debug("Got battery state 0 for '%s' (%s)", device_name, data["mac"])



    def status_update(self):
        _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))
        import Zemismart
        
        for device_name, data in self.devices.items():
            _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), device_name, data["mac"])
            
            shade = Zemismart.Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout, withMutex=True)
            with shade:
                device_state = self.get_device_state(device_name, data, shade)

                yield [
                    MqttMessage(
                        topic=self.format_topic(device_name), 
                        payload=json.dumps(device_state)
                    ),
                    MqttMessage(
                        topic=self.format_topic(device_name, "currentPosition"), 
                        payload=device_state["currentPosition"]
                    ),
                    MqttMessage(
                        topic=self.format_topic(device_name, "battery"), 
                        payload=device_state["battery"]
                    ),
                    # TODO: How to get this state?
                    MqttMessage(
                        topic=self.format_topic(device_name, "positionState"), 
                        payload=device_state["positionState"]
                    )
                ]

    def on_command(self, topic, value):
        _LOGGER.info("On command called with %s %s", topic, value)
        import Zemismart

        topic_without_prefix = topic.replace("{}/".format(self.topic_prefix), "")
        device_name, action = topic_without_prefix.split("/")

        if device_name in self.devices:
            data = self.devices[device_name]
            _LOGGER.debug("On command got device %s %s", device_name, data)
        else:
            logger.log_exception(_LOGGER, "Ignore command because device %s is unknown", device_name)
            return []

        value = value.decode("utf-8")
        if action == "targetPosition":
            self.last_target_position = int(value)
            shade = Zemismart.Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout, withMutex=True)
            with shade:

                # get the current state so we can work out direction for update messages
                device_state = self.get_device_state(device_name, data, shade)
                device_position = device_state["currentPosition"]

                if device_position == int(value):
                    # no update required, not moved
                    _LOGGER.debug("Position for device '%s' (%s) matches, %s %s",  
                            device_name, data["mac"], device_position, value)
                    return[]
                else:
                    # work out the direction
                    if device_position < int(value):
                        direction = "DECREASING"
                    else:
                        direction = "INCREASING"

                    # send the new position
                    shade.set_position(int(value))

                    # Until we reach a point where the position stops moving, send
                    # updated state messages
                    # Setting this to a large invalid value so we get at least one update
                    device_position = 255
                    while device_position != shade.position or self.last_target_position != int(value):
                        _LOGGER.debug("Moving %s device '%s' (%s), %s %s %s", repr(self), 
                            device_name, data["mac"], direction, device_position, shade.position)

                        device_state = {
                            "currentPosition": shade.position,
                            "targetPosition": int(value),
                            "battery": shade.battery,
                            "positionState": direction
                        }
                        yield [
                            MqttMessage(
                                topic=self.format_topic(device_name), 
                                payload=json.dumps(device_state)
                            )
                        ]
                        device_position = shade.position
                        # SLEEP 1s, if shade is moving it's position will
                        # have changed when we loop back around
                        time.sleep(1)

                    # Device has finished updating, return one last message saying we stopped
                    # if we were not interupted
                    if self.last_target_position == int(value):
                        device_state = {
                            "currentPosition": device_position,
                            "targetPosition": int(value),
                            "battery": shade.battery,
                            "positionState": "STOPPED"
                        }
                        return [
                            MqttMessage(
                                topic=self.format_topic(device_name), 
                                payload=json.dumps(device_state)
                            )
                        ]
                    else:
                        # interupted by a different update, return
                        return []

        elif action == "get":
            shade = Zemismart.Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout, withMutex=True)
            with shade:
                device_state = self.get_device_state(device_name, data, shade)

                return [
                    MqttMessage(
                        topic=self.format_topic(device_name), 
                        payload=json.dumps(device_state)
                    ),
                    MqttMessage(
                        topic=self.format_topic(device_name, "currentPosition"), 
                        payload=device_state["currentPosition"]
                    ),
                    MqttMessage(
                        topic=self.format_topic(device_name, "battery"), 
                        payload=device_state["battery"]
                    ),
                    # TODO: How to get this state?
                    MqttMessage(
                        topic=self.format_topic(device_name, "positionState"), 
                        payload='STOPPED'
                    )
                ]
        else: 
            return []

    