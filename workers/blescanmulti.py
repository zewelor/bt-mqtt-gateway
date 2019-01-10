import time
from interruptingcow import timeout
from bluepy.btle import Scanner, DefaultDelegate
from mqtt import MqttMessage
import mqtt
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
    present = False
    for dev in devices:
      if dev.addr == mac.lower():
         present = True

    return present

  def getrssi(self, devices, mac):
    rssivalue = -999
    for dev in devices:
      if dev.addr == mac.lower():
         rssivalue = dev.rssi

    return rssivalue

  def status_update(self):
    scanner = Scanner().withDelegate(ScanDelegate())
    devices = scanner.scan(10.0)
    ret = []

    for name, mac in self.devices.items():
      try:
        if self.searchmac(devices, mac):
          ret.append(MqttMessage(topic=self.format_topic('presence/'+name+'/rssi'), payload=str(self.getrssi(devices,mac))))
          ret.append(MqttMessage(topic=self.format_topic('presence/'+name), payload="1"))
        else:
          ret.append(MqttMessage(topic=self.format_topic('presence/'+name), payload="0"))
      except RuntimeError:
        pass

    return ret
