import time
from interruptingcow import timeout
from bluepy.btle import Scanner, DefaultDelegate
from mqtt import MqttMessage
from utils import booleanize
from workers.base import BaseWorker
from logger import _LOGGER

REQUIREMENTS = ['bluepy']


class ScanDelegate(DefaultDelegate):
  def __init__(self):
    DefaultDelegate.__init__(self)

  def handleDiscovery(self, dev, isNewDev, isNewData):
    if isNewDev:
      _LOGGER.debug("Discovered new device: %s" % dev.addr)


class BlescanmultiWorker(BaseWorker):
  # Default values
  devices = {}
  available_payload = 'home'  # type: str
  unavailable_payload = 'not_home'  # type: str
  available_timeout = 0  # type: float
  unavailable_timeout = 60  # type: float
  scan_timeout = 10.  # type: float
  scan_passive = True  # type: bool

  def searchmac(self, devices, mac):
    for dev in devices:
      if dev.addr == mac.lower():
         return dev

    return None

  def status_update(self):
    scanner = Scanner().withDelegate(ScanDelegate())
    devices = scanner.scan(float(self.scan_timeout), passive=booleanize(self.scan_passive))
    ret = []

    for name, mac in self.devices.items():
      device = self.searchmac(devices, mac)
      if device is None:
        ret.append(MqttMessage(topic=self.format_topic('presence/'+name), payload="0"))
      else:
        ret.append(MqttMessage(topic=self.format_topic('presence/'+name+'/rssi'), payload=device.rssi))
        ret.append(MqttMessage(topic=self.format_topic('presence/'+name), payload="1"))

    return ret
