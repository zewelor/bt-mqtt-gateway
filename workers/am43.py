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
    target_range_scale = 3 # type: int
    last_target_position = 255

    def _setup(self):
        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))

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
                target_position = self.correct_value(data, self.last_target_position)

                return {
                    "currentPosition": shade_position,
                    "targetPosition": target_position,
                    "battery": shade.battery,
                    "positionState": "STOPPED"
                }
            else:
                _LOGGER.debug("Got battery state 0 for '%s' (%s)", device_name, data["mac"])

    def create_mqtt_messages(self, device_name, device_state):

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
                topic=self.format_topic(device_name, "targetPosition"), 
                payload=device_state["targetPosition"]
            ),
            MqttMessage(
                topic=self.format_topic(device_name, "battery"), 
                payload=device_state["battery"]
            ),
            MqttMessage(
                topic=self.format_topic(device_name, "positionState"), 
                payload=device_state["positionState"]
            )
        ]

    def single_device_status_update(self, device_name, data):
        import Zemismart

        _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), device_name, data["mac"])
            
        shade = Zemismart.Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout, withMutex=True)
        try:
            with shade:
                device_state = self.get_device_state(device_name, data, shade)
                return self.create_mqtt_messages(device_name, device_state)

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

        topic_without_prefix = topic.replace("{}/".format(self.topic_prefix), "")
        device_name, field, action = topic_without_prefix.split("/")

        if device_name in self.devices:
            data = self.devices[device_name]
            _LOGGER.debug("On command got device %s %s", device_name, data)
        else:
            logger.log_exception(_LOGGER, "Ignore command because device %s is unknown", device_name)
            return []

        value = value.decode("utf-8")
        if field == "targetPosition" and action == "set":

            # internal state of the target position should align with the scale used by the
            # device
            target_position = self.correct_value(data, int(value))
            self.last_target_position = target_position

            shade = Zemismart.Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout, withMutex=True)
            try:
                with shade:

                    # get the current state so we can work out direction for update messages
                    # after getting this, convert so we are using the device scale for
                    # values
                    device_state = self.get_device_state(device_name, data, shade)
                    device_position = self.correct_value(data, device_state["currentPosition"])

                    if device_position == target_position:
                        # no update required, not moved
                        _LOGGER.debug("Position for device '%s' (%s) matches, %s %s",  
                                device_name, data["mac"], device_position, value)
                        return[]
                    else:
                        # work out the direction
                        # this compares the values using the caller scale instead
                        # of the internal scale. 
                        if device_state["currentPosition"] < int(value):
                            direction = "DECREASING"
                        else:
                            direction = "INCREASING"

                        # send the new position
                        shade.set_position(target_position)

                        # Until we reach a point where the position stops moving, send
                        # updated state messages
                        # Setting this initially to a large invalid value so we get at least one update
                        device_position = 255
                        while not (target_position - self.target_range_scale) <= device_position <= (target_position + self.target_range_scale) or self.last_target_position != target_position:

                            _LOGGER.debug("Moving %s device '%s' (%s), %s %s %s %s", repr(self), 
                                device_name, data["mac"], direction, device_position, shade.position, target_position)

                            shade.update()
                            if device_position != shade.position:
                                # Initially thought this would send state updates as it goes,
                                # sends them all in bulk at the end!
                                # device_state = {
                                #     "currentPosition": self.correct_value(data, shade.position),
                                #     "targetPosition": int(value),
                                #     "battery": shade.battery,
                                #     "positionState": direction
                                # }
                                # yield self.create_mqtt_messages(device_name, device_state)

                                device_position = shade.position

                            # SLEEP 1s, if shade is moving it's position will
                            # have changed when we loop back around
                            time.sleep(1)
                        
                        _LOGGER.debug("%s Exited loop for device '%s' (%s), %s %s %s %s %s", repr(self), 
                                device_name, data["mac"], 
                                direction, device_position, shade.position, 
                                self.last_target_position, target_position)

                        # Device has finished updating, return one last message saying we stopped

                        # Also set the last target position, we won't always stop bang
                        # on where we targeted.
                        self.last_target_position = device_position

                        device_state = {
                            "currentPosition": self.correct_value(data, device_position),
                            "targetPosition": self.correct_value(data, device_position),
                            "battery": shade.battery,
                            "positionState": "STOPPED"
                        }
                        return self.create_mqtt_messages(device_name, device_state)
                            
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
                return []

        elif field == "get" or action == "get":
            return self.single_device_status_update(device_name, data)
        else: 
            return []

    