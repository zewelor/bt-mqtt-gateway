"""
worker for inkbird ibbq and other equivalent cooking/BBQ thermometers.

Thermometer sends every ~2sec the current temperature.

"""
import struct
from bluepy import btle

from mqtt import MqttMessage
from workers.base import BaseWorker
import logger
_LOGGER = logger.get(__name__)

REQUIREMENTS = ['bluepy']


class IbbqWorker(BaseWorker):

  def __init__(self, command_timeout, **args):
    self.command_timeout = command_timeout
    for arg, value in args.items():
      setattr(self, arg, value)
    self._setup()

  def _setup(self):
    _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
    for name, mac in self.devices.items():
      _LOGGER.info("Adding %s device '%s' (%s)", repr(self), name, mac)
      self.devices[name] = ibbqThermometer(mac, timeout=self.command_timeout)

  def format_static_topic(self, *args):
    return '/'.join([self.topic_prefix, *args])

  def __repr__(self):
    return self.__module__.split(".")[-1]

  def status_update(self):
    ret = list()
    value = list()
    for name, ibbq in self.devices.items():
      if not ibbq.connected:
        ibbq.device = ibbq.connect()
        ibbq.subscribe()
      if ibbq.connected:
        _LOGGER.debug("device %s connected", name)
        value = ibbq.update()
        if not value:
          return
      n = 0
      for i in value:
        n += 1
        ret.append(MqttMessage(topic=self.format_static_topic(name, str(n)), payload=i))
      return(ret)


class ibbqThermometer():
  AccountAndVerify = 'fff2'
  RealTimeData = 'fff4'
  SettingData = 'fff5'
  Notify = b'\x01\x00'
  realTimeDataEnable = bytearray([0x0B, 0x01, 0x00, 0x00, 0x00, 0x00])
  KEY = bytearray([0x21, 0x07, 0x06, 0x05, 0x04, 0x03, 0x02, 0x01,
           0xb8, 0x22, 0x00, 0x00, 0x00, 0x00, 0x00])

  def __init__(self, mac, timeout=5):
    self.timeout = timeout
    self.mac = mac
    self.values = list()
    self.device = self.connect()
    self.offline = 0
    if not self.device:
      return
    self.device = self.subscribe()

  @property
  def connected(self):
    return(bool(self.device))

  def connect(self, timeout=5):
    try:
      return(btle.Peripheral(self.mac))
    except btle.BTLEDisconnectError as er:
      _LOGGER.debug("failed connect %s", er)

  def subscribe(self, timeout=5):
    if self.device is None:
      return
    try:
      services = self.device.getServices()
      for service in services:
        if "fff0" not in str(service.uuid):
          continue
        for schar in service.getCharacteristics():
          if self.AccountAndVerify in str(schar.uuid):
            account_uuid = schar
          if self.RealTimeData in str(schar.uuid):
            RT_uuid = schar
          if self.SettingData in str(schar.uuid):
            Setting_uuid = schar
      account_uuid.write(self.KEY)
      _LOGGER.info("Authenticated %s", self.mac)
      self.device.writeCharacteristic(RT_uuid.getHandle() + 1, self.Notify)
      Setting_uuid.write(self.realTimeDataEnable)
      self.device.withDelegate(MyDelegate(self))
      _LOGGER.info("enable RT and enabled notify for %s", self.mac)
      self.offline = 0
    except btle.BTLEException as ex:
      _LOGGER.info("failed %s %s", self.mac, ex)
      self.device = None
      _LOGGER.info("unsubscribe")
    return self.device

  def update(self):
    if not self.connected:
      return
    self.values = None
    try:
      while self.device.waitForNotifications(0.1):
        pass
      _LOGGER.debug("update succeeded")
      if self.values:
        self.offline = 0
        return(self.values)
      else:
        _LOGGER.debug("%s is silent", self.mac)
        if self.offline > 1:
          try:
            self.device.disconnect()
          except btle.BTLEInternalError:
            pass
          self.device = None
          _LOGGER.debug("%s reconnect", self.mac)
        else:
          self.offline += 1
    except btle.BTLEDisconnectError as e:
      _LOGGER.debug("%s", e)
      self.device = None


class MyDelegate(btle.DefaultDelegate):

  def __init__(self, caller):
    btle.DefaultDelegate.__init__(self)
    self.caller = caller

  def handleNotification(self, cHandle, data):
    result = []
    safe = data
    while (len(data) > 0):
      v, data = data[0:2], data[2:]
      result.append(struct.unpack('<H', v)[0]/10)
    self.caller.values = result
    _LOGGER.debug("called handler %s %s", result, safe)
