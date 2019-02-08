import time
from interruptingcow import timeout
from bluepy.btle import Scanner, DefaultDelegate
from mqtt import MqttMessage
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
  def searchmac(self, devices, mac):
    for dev in devices:
      if dev.addr == mac.lower():
         return dev

    return None

  def status_update(self, poll_device=None):
    scanner = Scanner().withDelegate(ScanDelegate())
    devices = scanner.scan(10.0)
    ret = []

    for name, mac in self.devices.items():
      if poll_device and name != poll_device:
        continue
      device = self.searchmac(devices, mac)
      if device is None:
        ret.append(MqttMessage(topic=self.format_topic('presence/'+name), payload="0"))
      else:
        ret.append(MqttMessage(topic=self.format_topic('presence/'+name+'/rssi'), payload=device.rssi))
        ret.append(MqttMessage(topic=self.format_topic('presence/'+name), payload="1"))

    return ret
