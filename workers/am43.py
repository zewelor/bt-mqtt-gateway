from const import DEFAULT_PER_DEVICE_TIMEOUT

import logger
from mqtt import MqttMessage
from workers.base import BaseWorker

_LOGGER = logger.get(__name__)

REQUIREMENTS = [
    "git+https://github.com/GylleTanken/python-zemismart-roller-shade.git@36738c72d7382e78e1223c8ae569acab10f498e6#egg=Zemismart"
]

class Am43Worker(BaseWorker):

    per_device_timeout = DEFAULT_PER_DEVICE_TIMEOUT  # type: int

    def _setup(self):
        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))


    def status_update(self):
        _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))
        import Zemismart
        
        for device_name, data in self.devices.items():
            _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), device_name, data["mac"])
            
            shade = Zemismart.Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout)
            with shade:

                battery = 0
                retry_attempts = 0
                while battery == 0 and retry_attempts < 5:
                    # The docs for this library say that sometimes this needs called
                    # multiple times, try up to 5 until we get a battery number
                    shade.update()

                    battery = shade.battery

                    if battery > 0:

                        yield [
                            MqttMessage(
                                topic=self.format_topic(device_name, "currentPosition"), payload=shade.position
                            ),
                            MqttMessage(
                                topic=self.format_topic(device_name, "battery"), payload=shade.battery
                            ),
                            # TODO: How to get this state?
                            MqttMessage(
                                topic=self.format_topic(device_name, "positionState"), payload='STOPPED'
                            )
                        ]
                    else:
                        _LOGGER.debug("Got battery state 0 for '%s' (%s)", device_name, data["mac"])

    def on_command(self, topic, value):
        _LOGGER.info("On command called with %s %s", topic, value)
        import Zemismart

        topic_without_prefix = topic.replace("{}/".format(self.topic_prefix), "")
        device_name, action = topic_without_prefix.split("/")
        # TODO: targetPosition

        if device_name in self.devices:
            data = self.devices[device_name]
        else:
            logger.log_exception(_LOGGER, "Ignore command because device %s is unknown", device_name)
            return []

        value = value.decode("utf-8")
        if action == "targetPosition":
            shade = Zemismart.Zemismart(data["mac"], data["pin"], max_connect_time=self.per_device_timeout)
            with shade:
                shade.set_position(int(value))

        # TODO: Return updated state messages?
        # need to:
        # - get the current position before setting
        # - update for ascending / descending based on if the target is higher or lower
        # - loop (with sleeps) until current = target? As it looks like the library will get updates 
        #   while it is in the "with shade" context

        return []
