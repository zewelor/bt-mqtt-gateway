from datetime import datetime
import time
from interruptingcow import timeout

from exceptions import DeviceTimeoutError
from mqtt import MqttMessage
from workers.base import BaseWorker

REQUIREMENTS = ["bluepy"]


# Bluepy might need special settings
# sudo setcap 'cap_net_raw,cap_net_admin+eip' /usr/local/lib/python3.6/dist-packages/bluepy/bluepy-helper


class MiscaleWorker(BaseWorker):

    SCAN_TIMEOUT = 5

    def status_update(self):
        results = self._get_data()
        messages = [MqttMessage(topic=self.format_topic("weight/" + results.unit), payload=results.weight)]
        if results.impedance:
            messages.append(MqttMessage(topic=self.format_topic("impedance"), payload=results.impedance))
        if results.datetime:
            messages.append(MqttMessage(topic=self.format_topic("datetime"), payload=results.datetime))

        return messages

    def _get_data(self):
        from bluepy import btle

        scan_processor = ScanProcessor(self.mac)
        scanner = btle.Scanner().withDelegate(scan_processor)
        scanner.scan(self.SCAN_TIMEOUT, passive=True)

        with timeout(
            self.SCAN_TIMEOUT,
            exception=DeviceTimeoutError(
                "Retrieving data from {} device {} timed out after {} seconds".format(
                    repr(self), self.mac, self.SCAN_TIMEOUT
                )
            ),
        ):
            while not scan_processor.ready:
                time.sleep(1)
            return scan_processor.results

        return scan_processor.results


class ScanProcessor:
    def __init__(self, mac):
        self._ready = False
        self._mac = mac
        self._results = MiWeightScaleData()

    def handleDiscovery(self, dev, isNewDev, _):
        if dev.addr == self.mac.lower() and isNewDev:
            for (sdid, desc, data) in dev.getScanData():

                # Xiaomi Scale V1
                if data.startswith("1d18") and sdid == 22:
                    measunit = data[4:6]
                    measured = int((data[8:10] + data[6:8]), 16) * 0.01
                    unit = ""

                    if measunit.startswith(("03", "b3")):
                        unit = "lbs"
                    elif measunit.startswith(("12", "b2")):
                        unit = "jin"
                    elif measunit.startswith(("22", "a2")):
                        unit = "kg"
                        measured = measured / 2

                    self.results.weight = round(measured, 2)
                    self.results.unit = unit

                    self.ready = True

                # Xiaomi Scale V2
                if data.startswith("1b18") and sdid == 22:
                    measunit = data[4:6]
                    measured = int((data[28:30] + data[26:28]), 16) * 0.01
                    unit = ""

                    if measunit == "03":
                        unit = "lbs"
                    elif measunit == "02":
                        unit = "kg"
                        measured = measured / 2

                    datetime = datetime.strptime(
                        str(int((data[10:12] + data[8:10]), 16))
                        + " "
                        + str(int((data[12:14]), 16))
                        + " "
                        + str(int((data[14:16]), 16))
                        + " "
                        + str(int((data[16:18]), 16))
                        + " "
                        + str(int((data[18:20]), 16))
                        + " "
                        + str(int((data[20:22]), 16)),
                        "%Y %m %d %H %M %S"
                    )

                    self.results.weight = round(measured, 2)
                    self.results.unit = unit
                    self.results.impedance = str(int((data[24:26] + data[22:24]), 16))
                    self.results.datetime = str(datetime)

                    self.ready = True

    @property
    def mac(self):
        return self._mac

    @property
    def ready(self):
        return self._ready

    @ready.setter
    def ready(self, var):
        self._ready = var

    @property
    def results(self):
        return self._results


class MiWeightScaleData:
    def __init__(self):
        self._weight = None
        self._unit = None
        self._datetime = None
        self._impedance = None

    @property
    def weight(self):
        return self._weight

    @weight.setter
    def weight(self, var):
        self._weight = var

    @property
    def unit(self):
        return self._unit

    @unit.setter
    def unit(self, var):
        self._unit = var

    @property
    def datetime(self):
        return self._datetime

    @datetime.setter
    def datetime(self, var):
        self._datetime = var

    @property
    def impedance(self):
        return self._impedance

    @impedance.setter
    def impedance(self, var):
        self._impedance = var
