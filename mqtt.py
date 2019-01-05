import paho.mqtt.client as mqtt
from logger import _LOGGER

LWT_ONLINE = 'online'
LWT_OFFLINE = 'offline'

class MqttClient:

  def __init__(self, config):
    self._config = config
    self._mqttc = mqtt.Client(client_id=self.client_id,
                              clean_session=False,
                              userdata = {'global_topic_prefix': self.topic_prefix})

    if self.username and self.password:
      self.mqttc.username_pw_set(self.username, self.password)

    if self.availability_topic:
      topic = self._format_topic(self.availability_topic)
      _LOGGER.debug("Setting LWT to: %s" % topic)
      self.mqttc.will_set(topic, payload=LWT_OFFLINE, retain=True)

  def publish(self, messages):
    if not messages:
      return

    for m in messages:
      topic = self._format_topic(m.topic)
      self.mqttc.publish(topic, m.payload, retain=m.retain)

  @property
  def client_id(self):
    return self._config['client_id'] if 'client_id' in self._config else 'bt-mqtt-gateway'

  @property
  def hostname(self):
    return self._config['host']

  @property
  def port(self):
    return self._config['port'] if 'port' in self._config else 1883

  @property
  def username(self):
    return self._config['username'] if 'username' in self._config else None

  @property
  def password(self):
    return self._config['password'] if 'password' in self._config else None

  @property
  def topic_prefix(self):
    return self._config['topic_prefix'] if 'topic_prefix' in self._config else None

  @property
  def availability_topic(self):
    return self._config['availability_topic'] if 'availability_topic' in self._config else None

  @property
  def mqttc(self):
    return self._mqttc

  def callbacks_subscription(self, callbacks):
    self.mqttc.connect(self.hostname, port=self.port)

    for topic, callback in callbacks:
      topic = self._format_topic(topic)
      _LOGGER.debug("Subscribing to: %s" % topic)
      self.mqttc.message_callback_add(topic, callback)
      self.mqttc.subscribe(topic)

    self.mqttc.loop_start()

    if self.availability_topic:
      self.publish([MqttMessage(topic=self.availability_topic, payload=LWT_ONLINE, retain=True)])

  def __del__(self):
    if self.availability_topic:
      self.publish([MqttMessage(topic=self.availability_topic, payload=LWT_OFFLINE, retain=True)])

  def _format_topic(self, topic):
    return "{}/{}".format(self.topic_prefix, topic) if self.topic_prefix else topic

class MqttMessage:
  def __init__(self, topic=None, payload=None, retain=False):
    self._topic = topic
    self._payload = payload
    self._retain = retain

  @property
  def topic(self):
    return self._topic

  @topic.setter
  def topic(self, new_topic):
    self._topic = new_topic

  @property
  def payload(self):
    return self._payload

  @property
  def retain(self):
    return self._retain

  @property
  def as_dict(self):
    return {
      'topic': self.topic,
      'payload': self.payload
    }

  def __repr__(self):
    return self.as_dict.__str__()

  def __str__(self):
    return self.__repr__()
