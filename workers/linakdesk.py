from interruptingcow import timeout

from mqtt import MqttMessage
from workers.base import BaseWorker

REQUIREMENTS = ['git+https://github.com/zewelor/linak_bt_desk.git@aa9412f98b3044be34c70e89d02721e6813ea731#egg=linak_bt_desk']

class LinakdeskWorker(BaseWorker):

  SCAN_TIMEOUT = 20

  def _setup(self):
    from linak_dpg_bt import LinakDesk

    self.desk = LinakDesk(self.mac)

  def status_update(self):
    return [MqttMessage(topic=self.format_topic('height/cm'), payload=self._get_height())]

  def _get_height(self):
    with timeout(SCAN_TIMEOUT, exception=TimeoutError('Retrieving the height from {} device {} timed out after {} seconds'.format(repr(self), self.mac, SCAN_TIMEOUT))):
      self.desk.read_dpg_data()
      return self.desk.current_height_with_offset.cm

    return -1

