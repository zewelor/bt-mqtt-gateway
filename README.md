# bt-mqtt-gateway

A simple Python script which provides a Bluetooth to MQTT gateway, easily extensible via custom workers.  
See [Wiki](https://github.com/zewelor/bt-mqtt-gateway/wiki) for more information.

## Features

* Highly extensible via custom workers
* Data publication via MQTT
* Configurable topic and payload
* MQTT authentication support
* Systemd service
* Reliable and intuitive
* Tested on Raspberry Pi Zero W

### Supported devices

* [EQ3 Bluetooth smart thermostat](http://www.eq-3.com/products/eqiva/bluetooth-smart-radiator-thermostat.html) via [python-eq3bt](https://github.com/rytilahti/python-eq3bt)
* [Xiaomi Mi Scale](http://www.mi.com/en/scale/)
* [Xiaomi Mi Scale v2 (Body Composition Scale)](https://www.mi.com/global/mi-body-composition-scale)
* [Linak Desk](https://www.linak.com/business-areas/desks/office-desks/) via [linak_bt_desk](https://github.com/zewelor/linak_bt_desk)
* [MySensors](https://www.mysensors.org/)
* [Xiaomi Mi Flora plant sensor](https://xiaomi-mi.com/sockets-and-sensors/xiaomi-huahuacaocao-flower-care-smart-monitor/) via [miflora](https://github.com/open-homeautomation/miflora)
* Xiaomi Aqara thermometer via [mithermometer](https://github.com/hobbypunk90/mithermometer)
* Bluetooth Low Power devices (BLE)
* [Oral-B connected toothbrushes](https://oralb.com/en-us/products#viewtype:gridview/facets:feature=feature-bluetooth-connectivity/category:products/page:0/sortby:Featured-Sort/productsdisplayed:undefined/promotilesenabled:undefined/cwidth:3/pscroll:)
* [Switchbot](https://www.switch-bot.com/)
* [Sensirion SmartGadget](https://www.sensirion.com/en/environmental-sensors/humidity-sensors/development-kit/) via [python-smartgadget](https://github.com/merll/python-smartgadget)
* [RuuviTag](https://ruuvi.com/ruuvitag-specs/) via [ruuvitag-sensor](https://github.com/ttu/ruuvitag-sensor)
* Xiaomi Mijia 2nd gen, aka LYWSD02

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

* `python3` >= 3.5
* `pip3`
* `git`

## Installation

### Virtualenv
On a modern Linux system, just a few steps are needed to get the gateway working.
The following example shows the installation under Debian/Raspbian:

```shell
sudo apt-get install git python3 python3-pip python3-wheel bluetooth bluez libglib2.0-dev
sudo pip3 install virtualenv
git clone https://github.com/zewelor/bt-mqtt-gateway.git
cd bt-mqtt-gateway
virtualenv -p python3 .venv
source .venv/bin/activate
sudo pip3 install -r requirements.txt
```

All needed python libs, per each worker, should be auto installed on run. If now you can install them manually:

```shell
pip3 install `./gateway.py -r configured`
```

### Docker
There are prebuilt docker images at https://hub.docker.com/r/zewelor/bt-mqtt-gateway/tags. 
Thanks @hobbypunk90 and @krasnoukhov for docker work.

Mount config.yaml as /config.yaml volume

Example exec

```shell
docker run -d --name bt-mqtt-gateway --network=host -v $PWD/config.yaml:/config.yaml zewelor/bt-mqtt-gateway
```

## Configuration

All worker configuration is done in the file [`config.yaml`](config.yaml.example).
Be sure to change all options for your needs.
This file needs to be created first:

```shell
cp config.yaml.example config.yaml
nano config.yaml
source .venv/bin/activate
sudo ./gateway.py
```

**Attention:**
You need to add at least one worker to your configuration.
Scan for available Bluetooth devices in your proximity with the command:

```shell
sudo hcitool lescan
```

## Execution

A test run is as easy as:

```shell
source .venv/bin/activate
sudo ./gateway.py
```

Debug output can be displayed using the `-d` argument:

```shell
sudo ./gateway.py -d
```

## Deployment

Continuous background execution can be done using the example Systemd service unit provided.
   
```shell
sudo cp bt-mqtt-gateway.service /etc/systemd/system/
sudo nano /etc/systemd/system/bt-mqtt-gateway.service (modify path of bt-mqtt-gateway)
sudo systemctl daemon-reload
sudo systemctl start bt-mqtt-gateway
sudo systemctl status bt-mqtt-gateway
sudo systemctl enable bt-mqtt-gateway
```

**Attention:**
You need to define the absolute path of `service.sh` in `bt-mqtt-gateway.service`.

**Testing mqtt:**
Use mosquitto_sub to print all messages
```
mosquitto_sub -h localhost -d -t # command also help for me to test MQTT messages
```

**Dynamically Changing the Update Interval**
To dynamically change the `update_interval` of a worker, publish a message containing the new interval in seconds at the `update_interval` topic. Note that the `update_interval` will revert back to the value in `config.yaml` when the gateway is restarted.
I.E:
```
# Set a new update interval of 3 minutes
mosquitto_pub -h localhost -t 'miflora/update_interval' -m '150'
# Set a new update interval of 30 seconds
mosquitto_pub -h localhost -t 'mithermometer/update_interval' -m '30'
```

## Custom worker development

Create custom worker in workers [directory](https://github.com/zewelor/bt-mqtt-gateway/tree/master/workers). 

### Example simple worker

```python
from mqtt import MqttMessage
from workers.base import BaseWorker

REQUIREMENTS = ['pip_packages']

class TimeWorker(BaseWorker):
  def _setup(self):
    self._some = 'variable'

  def status_update(self):
    from datetime import datetime
    
    return [MqttMessage(topic=self.format_topic('time'), payload=datetime.now())]
```

`REQUIREMENTS` add required pip packages, they will be installed on first run. Remember to import them in method, not on top of the file, because on initialization, that package won't exists. Unless installed outside of the gateway. Check status_update method
 
`_setup` method - add / declare needed variables.

`status_update` method - It will be called using specified update_interval
 
### Example config entry

Add config to the example [config](https://github.com/zewelor/bt-mqtt-gateway/blob/master/config.yaml.example):

```yaml
    timeworker:
      args:
        topic_prefix: cool_time_worker
      update_interval: 1800
```

Variables set in args section will be set as object attributes in [BaseWorker.__init__](https://github.com/zewelor/bt-mqtt-gateway/blob/master/workers/base.py#L2)

topic_prefix, if specified, will be added to each mqtt message. Alongside with global_prefix set for gateway

## Troubleshooting
[See the Troubleshooting Wiki](https://github.com/zewelor/bt-mqtt-gateway/wiki/Troubleshooting)

## Built With

* [Python](https://www.python.org/) - The high-level programming language for general-purpose programming

## Authors

* [**zewelor**](https://github.com/zewelor) - *Initial work*
* [**bbbenji**](https://github.com/bbbenji) - *Minor contributions*
* [**elviosebastianelli**](https://github.com/elviosebastianelli) - *BLEscanmulti*
* [**jumping2000**](https://github.com/jumping2000) - *BLEscan*
* [**AS137430**](https://github.com/AS137430) - *Switchbot*


## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
