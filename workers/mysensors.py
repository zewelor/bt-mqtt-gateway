from mqtt import MqttMessage

from workers.base import BaseWorker
import logger

REQUIREMENTS = ["pyserial"]
_LOGGER = logger.get(__name__)


class MysensorsWorker(BaseWorker):
    def run(self, mqtt):
        import serial

        with serial.Serial(self.port, self.baudrate, timeout=10) as ser:
            _LOGGER.debug("Starting mysensors at: %s" % ser.name)
            while True:
                line = ser.readline()
                if not line:
                    continue
                splited_line = self.format_topic(line.decode("utf-8").strip()).split(
                    ";"
                )
                topic = "/".join(splited_line[0:-1])
                payload = "".join(splited_line[-1])
                mqtt.publish([MqttMessage(topic=topic, payload=payload)])
