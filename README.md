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
* [Linak Desk](https://www.linak.com/business-areas/desks/office-desks/) via [linak_bt_desk](https://github.com/zewelor/linak_bt_desk)
* [MySensors](https://www.mysensors.org/)
* [Xiaomi Mi Flora plant sensor](https://xiaomi-mi.com/sockets-and-sensors/xiaomi-huahuacaocao-flower-care-smart-monitor/) via [miflora](https://github.com/open-homeautomation/miflora)
* Xiaomi Aqara thermometer via [mithermometer](https://github.com/hobbypunk90/mithermometer)

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

* `python3` >= 3.5
* `pip3`

## Installation

On a modern Linux system, just a few steps are needed to get the gateway working.
The following example shows the installation under Debian/Raspbian:

```shell
sudo apt-get install git python3 python3-pip bluetooth bluez
git clone https://github.com/zewelor/bt-mqtt-gateway.git
cd bt-mqtt-gateway
sudo pip3 install -r requirements.txt
```

## Configuration

All worker configuration is done in the file [`config.yaml`](config.yaml.example).
This file needs to be created first:

```shell
cp config.yaml.example config.yaml
vim config.yaml
./gateway.py
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
sudo vim /etc/systemd/system/bt-mqtt-gateway.service
sudo systemctl daemon-reload
sudo systemctl start bt-mqtt-gateway
sudo systemctl status bt-mqtt-gateway
sudo systemctl enable bt-mqtt-gateway
```

**Attention:**
You need to define the absolute path of `gateway.py` in `bt-mqtt-gateway.service`.

## Custom worker development



## Built With

* [Python](https://www.python.org/) - The high-level programming language for general-purpose programming

## Authors

* [**zewelor**](https://github.com/zewelor) - *Initial work*
* [**bbbenji**](https://github.com/bbbenji) - *Minor contributions*

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
