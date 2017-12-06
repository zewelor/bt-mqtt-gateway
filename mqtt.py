import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt


class MqttClient:
  def __init__(self, config):
    self._config = config

  def publish(self, messages):
    if messages is None:
      return

    publish.multiple(list(map(lambda m: m.as_dict, messages)),
                     hostname=self.hostname,
                     auth={'username': self.username, 'password': self.password})

  @property
  def hostname(self):
    return self._config['host']

  @property
  def username(self):
    return self._config['username']

  @property
  def password(self):
    return self._config['password']

  def callbacks_subscription(self, callbacks):
    mqttc = mqtt.Client()

    mqttc.username_pw_set(self.username, self.password)
    mqttc.connect(self.hostname)

    for topic, callback in callbacks:
      mqttc.message_callback_add(topic, callback)
      mqttc.subscribe(topic)

    mqttc.loop_start()


class MqttMessage:
  def __init__(self, topic=None, payload=None):
    self._topic = topic
    self._payload = payload

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
  def as_dict(self):
    return {
      'topic': self.topic,
      'payload': self.payload
    }

  def __repr__(self):
    return self.as_dict.__str__()

  def __str__(self):
    return self.__repr__()
