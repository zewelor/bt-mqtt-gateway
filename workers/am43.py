from interruptingcow import timeout

from const import DEFAULT_PER_DEVICE_TIMEOUT

import logger
from exceptions import DeviceTimeoutError
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
        
        for name, data in self.devices.items():
            _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, data["mac"])
            
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
                                topic=self.format_topic(name, "currentPosition"), payload=shade.position
                            ),
                            MqttMessage(
                                topic=self.format_topic(name, "battery"), payload=shade.battery
                            )
                        ]
                    else:
                        _LOGGER.debug("Got battery state 0 for '%s' (%s)", name, data["mac"])

    def on_command(self, topic, value):
        _LOGGER.info("On command called with %s %s", topic, value)

        # TODO: targetPosition
