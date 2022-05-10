from mqtt import MqttMessage, MqttConfigMessage
from workers.base import BaseWorker
from enum import Enum
import logger
import asyncio
import platform

REQUIREMENTS = ["bleak"]
_LOGGER = logger.get(__name__)
SHORT_WAIT = 0.1


class UUID(Enum):
    WriteService = "0000AE00-0000-1000-8000-00805f9b34fb"
    NotifyService = "0000AE00-0000-1000-8000-00805f9b34fb"
    WriteCharacterstic = "0000AE03-0000-1000-8000-00805f9b34fb"
    NotifyCharacteristic = "0000AE04-0000-1000-8000-00805f9b34fb"


class BluetoothCommand(Enum):
    Up = "F30C"  # 243, 12
    Down = "F20D"  # 242, 13
    Stop = "F00F"  # 240, 15
    Power = "FF00"  # 255, 0
    Mode = "FE01"  # 254, 1
    Pause = "FB04"  # 251, 4
    B = "F609"  # 246, 9


class LiftState(Enum):
    Opened = "open"
    Closed = "clos"


class OsakaWorker(BaseWorker):
    lift_state = LiftState.Closed

    name: str
    device = None
    address = ""

    def _setup(self):
        return asyncio.get_event_loop().run_until_complete(self.find_client())

    async def find_client(self):
        from bleak import BleakError, BleakScanner, BleakClient

        def device_filter(d, ad):
            if d.name is None:
                return False

            if hasattr(self, "ble_device_name"):
                return d.name == self.ble_device_name

            return d.name.startswith("OSAKA_BLE")

        device = await BleakScanner.find_device_by_filter(device_filter)

        if device is None:
            _LOGGER.debug("Couldnt find an Osaka device")
            return

        self.device = device
        self.address = device.address

        _LOGGER.debug(f"Found {device.name}")

        client = BleakClient(device)
        await client.connect()

        self.client = client

    def status_update(self):
        pass

    async def connect(self):
        if not self.client:
            _LOGGER.debug("Not connected")
            return False

        if not self.client.is_connected:
            await self.client.connect()
            await self.client.start_notify(
                UUID.NotifyCharacteristic.value, self.on_notification
            )

        return True

    def config(self, availability_topic):
        device = {
            "identifiers": [
                self.address,
                self.format_discovery_id(self.address, self.name),
            ],
            "manufacturer": "Dreams",
            "model": "Osaka",
            "name": self.format_discovery_name(self.name),
        }

        return [
            MqttConfigMessage(
                MqttConfigMessage.COVER,
                self.format_discovery_topic(self.address, self.name, "lift"),
                payload={
                    "device_class": "garage",
                    "unique_id": self.format_discovery_id(
                        "osaka", self.name, self.address
                    ),
                    "name": "Osaka TV Bed Lift",
                    "availability_topic": "{}/{}".format(
                        self.global_topic_prefix, availability_topic
                    ),
                    "device": device,
                    "state_topic": "~/state",
                    "command_topic": "~/set",
                    "~": self.format_prefixed_topic(self.name),
                },
            )
        ]

    def on_notification(self, sender, data):
        _LOGGER.debug("%s received '%s' from %s", repr(self), data, sender)

    def on_command(self, topic, raw_payload):
        from json import loads

        _, device_name, device_type, command = topic.split("/")

        if device_name != self.name:
            return

        try:
            payload = loads(raw_payload)
        except:
            payload = {}

        async def run():
            if device_type == "lift":
                return await self.lift_command(command, payload)
            elif device_type == "music":
                return await self.music_command(command, payload)

        return asyncio.get_event_loop().run_until_complete(run())

    async def send_command(self, command):
        import binascii

        connected = await self.connect()
        if connected:
            return await self.client.write_gatt_char(
                UUID.WriteCharacterstic.value,
                binascii.a2b_hex(f"55AAF50A{command.value}FE"),
            )

    def change_lift_state(self, new_state: LiftState):
        self.state = new_state
        return [
            MqttMessage(
                self.format_topic(self.name, "state"),
                payload=new_state.value,
                retain=True,
            )
        ]

    async def open(self):
        await asyncio.sleep(SHORT_WAIT)
        await self.send_command(BluetoothCommand.Up)
        await asyncio.sleep(self.full_extension_seconds)
        await self.stop()
        return self.change_lift_state(LiftState.Opened)

    async def close(self):
        await asyncio.sleep(SHORT_WAIT)
        await self.send_command(BluetoothCommand.Down)
        await asyncio.sleep(self.full_extension_seconds)
        await self.stop()
        return self.change_lift_state(LiftState.Closed)

    async def stop(self):
        await self.send_command(BluetoothCommand.Stop)
        # This is what the official client does
        await asyncio.sleep(SHORT_WAIT)
        await self.send_command(BluetoothCommand.Stop)
        return []

    async def lift_command(self, command):
        if command == "OPEN" and self.state == LiftState.Closed:
            return await self.open()
        elif command == "CLOSE" and self.state == LiftState.Opened:
            return await self.close()
        elif command == "STOP":
            return await self.stop()
        else:
            _LOGGER.debug(f"Unknown lift command {command}")

    async def music_command(self, command, payload):
        if command == "power":
            await self.send_command(BluetoothCommand.Power)
        elif command == "mode":
            await self.send_command(BluetoothCommand.Mode)
        elif command == "pause":
            await self.send_command(BluetoothCommand.Mode)
        elif command == "b":
            await self.send_command(BluetoothCommand.B)
