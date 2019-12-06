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
        return [
            MqttMessage(
                topic=self.format_topic("weight/kg"), payload=self._get_data()
            )
        ]

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
            while scan_processor.weight is None:
                time.sleep(1)
            return scan_processor.weight

        return -1


class ScanProcessor:
    def __init__(self, mac):
        self._mac = mac
        self._data = None

    def handleDiscovery(self, dev, isNewDev, _):
        if dev.addr == self.mac.lower() and isNewDev:
            for (sdid, desc, data) in dev.getScanData():

                # Xiaomi Scale V1
                if data.startswith('1d18') and sdid == 22:
                    measunit = data[4:6]
                    measured = int((data[8:10] + data[6:8]), 16) * 0.01
                    unit = ''

                    if measunit.startswith(('03', 'b3')): unit = 'lbs'
                    if measunit.startswith(('12', 'b2')): unit = 'jin'
                    if measunit.startswith(('22', 'a2')): unit = 'kg' ; measured = measured / 2

                    self._data = round(measured, 2)
                    # self._data = round(measured , 2), unit, "", ""

                # Xiaomi Scale V2
                if data.startswith('1b18') and sdid == 22:
                    measunit = data[4:6]
                    measured = int((data[28:30] + data[26:28]), 16) * 0.01
                    unit = ''

                    if measunit == "03": unit = 'lbs'
                    if measunit == "02": unit = 'kg' ; measured = measured / 2
                    # mitdatetime = datetime.strptime(str(int((data[10:12] + data[8:10]), 16)) + " " + str(int((data[12:14]), 16)) +" "+ str(int((data[14:16]), 16)) +" "+ str(int((data[16:18]), 16)) +" "+ str(int((data[18:20]), 16)) +" "+ str(int((data[20:22]), 16)), "%Y %m %d %H %M %S")
                    # miimpedance = str(int((data[24:26] + data[22:24]), 16))

                    self._data = round(measured, 2)
                    # self._data = round(measured , 2), unit, str(mitdatetime), miimpedance

    @property
    def mac(self):
        return self._mac

    @property
    def weight(self):
        return self._data
