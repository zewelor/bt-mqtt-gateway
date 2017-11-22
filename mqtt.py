from config import settings
import paho.mqtt.publish as publish

class MqttClient:
    def __init__(self):
        self._connected = False
        self._config = settings['mqtt']

    def publish(self, messages):
        print(messages)
        publish.multiple(messages, hostname=self.hostname, auth = {'username':self.username, 'password':self.password})

    @property
    def hostname(self):
        return self._config['host']

    @property
    def username(self):
        return self._config['username']

    @property
    def password(self):
        return self._config['password']
