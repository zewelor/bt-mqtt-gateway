from interruptingcow import timeout
from mqtt import MqttMessage
from workers.base import BaseWorker

REQUIREMENTS = ['git+https://github.com/open-homeautomation/miflora.git@84f39432082796412d05b754c948499a1ad710e7#egg=miflora', 'bluepy']

monitoredAttrs = ["temperature", "moisture", "light", "conductivity", "battery"]

class MifloraWorker(BaseWorker):
  def _setup(self):
    from miflora.miflora_poller import MiFloraPoller
    from btlewrap.bluepy import BluepyBackend

    for name, mac in self.devices.items():
      self.devices[name] = MiFloraPoller(mac, BluepyBackend)

  def status_update(self):
    ret = []
    for name, poller in self.devices.items():
      try:
        ret += self.update_device_state(name, poller)
      except RuntimeError:
        pass
    return ret

  @timeout(8.0)
  def update_device_state(self, name, poller):
    ret = []
    poller.clear_cache()
    for attr in monitoredAttrs:
      ret.append(MqttMessage(topic=self.format_topic(name, attr), payload=poller.parameter_value(attr)))
    return ret
