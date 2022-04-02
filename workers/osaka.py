from mqtt import MqttMessage
from workers.base import BaseWorker
from enum import Enum
import logger
import asyncio
import platform

REQUIREMENTS = ["bleak"]
_LOGGER = logger.get(__name__)

class UUID(Enum):
    WriteService = "0000AE00-0000-1000-8000-00805f9b34fb"
    NotifyService = "0000AE00-0000-1000-8000-00805f9b34fb"
    WriteCharacterstic = "0000AE03-0000-1000-8000-00805f9b34fb"
    NotifyCharacteristic = "0000AE04-0000-1000-8000-00805f9b34fb"

class Command(Enum):
    Up = "F30C" # 243, 12
    Down = "F20D" # 242, 13
    Stop = "F00F" # 240, 15
    Power = "F00"
    Mode = "E01"
    Pause = "B04"
    B = "609"


class OsakaWorker(BaseWorker):
    def _setup(self):
        self.address = self.uuid if platform.system() == "Darwin" else self.mac
        _LOGGER.debug("Adding %s device '%s' (%s)", repr(self), self.name, self.address)
        self.client = self.find_client(self.address)
        _LOGGER.debug(self.client)

    def find_client(self, address):
        from bleak import BleakError, BleakScanner, BleakClient

        async def run():
            device = await BleakScanner.find_device_by_address(address)

            if device is None:
                return

            client = BleakClient(device)
            await client.connect()
            return client

        return asyncio.get_event_loop().run_until_complete(run())

    def status_update(self):
        pass

    async def connect(self):
        if not self.client.is_connected:
            await self.client.connect()
            await self.client.start_notify(UUID.NotifyCharacteristic, self.on_notification)

    def on_notification(self, sender, data):
        _LOGGER.debug("%s received '%s' from %s", repr(self), data, sender)

    def on_command(self, topic, raw_payload):
        from json import loads

        _, device_name, command, subcommand = topic.split("/")

        if device_name != self.name:
            return

        try:
            payload = loads(raw_payload)
        except:
            payload = {}

        async def run():
            if command == "lift":
                return await self.lift_command(subcommand, payload)
            elif command == "music":
                return await self.music_command(subcommand, payload)

        return asyncio.get_event_loop().run_until_complete(run())

    async def send_command(self, command):
        import binascii
        await self.connect()
        return await self.client.write_gatt_char(UUID.WriteCharacterstic, binascii.a2b_hex(f"55AAF50A{command}FE"))

    async def stop_lift(self):
        await self.send_command(Command.Stop)
        await asyncio.sleep(0.1)
        return await self.send_command(Command.Stop)

    async def lift_command(self, direction, payload):
        if direction != "stop":
            duration = payload.get("duration", 20)
            instruction = Command.Up if direction == "up" else Command.Down

            await asyncio.sleep(0.5)
            await self.send_command(instruction)
            await asyncio.sleep(duration)

        await self.stop_lift()

        return []

    async def music_command(self, command, payload):
        if command == "power":
            await self.send_command(Command.Power)
        elif command == "mode":
            await self.send_command(Command.Mode)
        elif command == "pause":
            await self.send_command(Command.Mode)
        elif command == "b":
            await self.send_command(Command.B)
        
        return []