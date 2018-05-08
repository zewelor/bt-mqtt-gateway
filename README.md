# bt-mqtt-gateway

Python script which creates a Bluetooth to MQTT gateway. Includes example config for a Bluetooth thermostat.

## Supported devices

* [EQ3 Bluetooth smart thermostat](http://www.eq-3.com/products/eqiva/bluetooth-smart-radiator-thermostat.html) via [python-eq3bt](https://github.com/rytilahti/python-eq3bt)
* [Xiaomi Mi Scale](http://www.mi.com/en/scale/)
* [Linak Desk](https://www.linak.com/business-areas/desks/office-desks/) via [linak_bt_desk](https://github.com/zewelor/linak_bt_desk)
* [MySensors](https://www.mysensors.org/)

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

```
python3
pip3
python3-serial
```

### Installing

Clone repo

```
git clone https://github.com/zewelor/bt-mqtt-gateway.git
```

Install requirements

```
pip install -r requirements.txt
```

Copy and customize config file

```
cp config.yaml.example config.yaml
```

Run

```
./gateway.py
```

## Deployment

This project includes an example Systemd service unit. In order to use it, copy `bt-mqtt-gateway.service` to `/etc/systemd/system/`. Edit the new file to use the correct absolute script paths and enable/start it.

```
sudo systemctl enable bt-mqtt-gateway
```

```
sudo systemctl start bt-mqtt-gateway
```

## Built With

* [Python](https://www.python.org/) - The high-level programming language for general-purpose programming


## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/your/project/tags). 

## Authors

* [**zewelor**](https://github.com/zewelor) - *Initial work*
* [**bbbenji**](https://github.com/bbbenji) - *Minor contributions*


## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
