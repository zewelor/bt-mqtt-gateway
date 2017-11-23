import time

REQUIREMENTS = ['bluepy', 'interruptingcow']

class MiscaleWorker():
  def __init__(self, mac):
    self._mac = mac

  def status_update(self):
    return [{
      'topic': 'weight/kg',
      'payload': self._get_weight(),
    }]


  def _get_weight(self):
    from bluepy import btle
    from interruptingcow import timeout

    scan_processor = ScanProcessor(self._mac)
    scanner = btle.Scanner().withDelegate(scan_processor)
    scanner.scan(5, passive=True)

    with timeout(5):
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
