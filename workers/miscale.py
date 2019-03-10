import time
from interruptingcow import timeout

from mqtt import MqttMessage
from workers.base import BaseWorker

REQUIREMENTS = ['bluepy']


# Bluepy might need special settings
# sudo setcap 'cap_net_raw,cap_net_admin+eip' /usr/local/lib/python3.6/dist-packages/bluepy/bluepy-helper

class MiscaleWorker(BaseWorker):

  SCAN_TIMEOUT = 5

  def status_update(self):
    return [MqttMessage(topic=self.format_topic('weight/kg'), payload=self._get_weight())]

  def _get_weight(self):
    from bluepy import btle

    scan_processor = ScanProcessor(self.mac)
    scanner = btle.Scanner().withDelegate(scan_processor)
    scanner.scan(SCAN_TIMEOUT, passive=True)

    with timeout(SCAN_TIMEOUT, exception=TimeoutError('Retrieving the weight from {} device {} timed out after {} seconds'.format(repr(self), self.mac, SCAN_TIMEOUT))):
      while scan_processor.weight is None:
        time.sleep(1)
      return scan_processor.weight

    return -1


class ScanProcessor():
  def __init__(self, mac):
    self._mac = mac
    self._weight = None

  def handleDiscovery(self, dev, isNewDev, _):
    if dev.addr == self.mac.lower() and isNewDev:
      for (sdid, desc, data) in dev.getScanData():
        if data.startswith('1d18') and sdid == 22:
          measured = int((data[8:10] + data[6:8]), 16) * 0.01

          self._weight = round(measured / 2, 2)

  @property
  def mac(self):
    return self._mac

  @property
  def weight(self):
    return self._weight
