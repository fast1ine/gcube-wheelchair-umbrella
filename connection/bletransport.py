import asyncio
import threading
import time


class BleSerialTransport:
    SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
    WRITE_CHUNK_SIZE = 20

    def __init__(self, address, name=None, connect_timeout=15):
        self.address = address
        self.name = name or address
        self.port = address
        self.timeout = None
        self.is_open = False
        self._connect_timeout = connect_timeout
        self._client = None
        self._loop = None
        self._loop_thread = None
        self._read_buffer = bytearray()
        self._read_condition = threading.Condition()
        self._write_lock = threading.Lock()
        self._cancelled = False
        self._start_loop()
        self._run(
            self._connect(),
            timeout=connect_timeout + min(connect_timeout, 10) + 10,
        )

    @classmethod
    def scan(cls, timeout=5, group_label=None):
        async def discover():
            from bleak import BleakScanner

            found = await BleakScanner.discover(timeout=timeout, return_adv=True)
            devices = []
            for device, advertisement in found.values():
                name = advertisement.local_name or device.name or ""
                if "PINGPONG." not in name.upper() or "AIR" not in name.upper():
                    continue
                if group_label and not cls._matches_group(name, group_label):
                    continue
                devices.append({"address": device.address, "name": name})
            return sorted(devices, key=lambda item: item["name"])

        return asyncio.run(discover())

    @staticmethod
    def _matches_group(name, group_label):
        label = str(group_label).upper()
        prefix = "PINGPONG." if label == "00" else "PINGPONG.{}".format(label)
        upper_name = name.upper()
        return prefix in upper_name and "AIR" in upper_name

    def reconnect(self):
        self._cancelled = False
        self._start_loop()
        self._run(
            self._connect(),
            timeout=self._connect_timeout + min(self._connect_timeout, 10) + 10,
        )

    def read(self, size=1):
        if size <= 0:
            return b""
        deadline = None if self.timeout is None else time.monotonic() + self.timeout
        with self._read_condition:
            while len(self._read_buffer) < size and self.is_open and not self._cancelled:
                wait_time = None
                if deadline is not None:
                    wait_time = deadline - time.monotonic()
                    if wait_time <= 0:
                        break
                self._read_condition.wait(wait_time)
            count = min(size, len(self._read_buffer))
            data = bytes(self._read_buffer[:count])
            del self._read_buffer[:count]
            return data

    def write(self, data):
        payload = bytes(data)
        if not payload:
            return 0
        if not self.is_open:
            raise RuntimeError("Bluetooth LE device is not connected.")
        with self._write_lock:
            self._run(self._write(payload), timeout=10)
        return len(payload)

    def cancel_read(self):
        self._cancelled = True
        with self._read_condition:
            self._read_condition.notify_all()

    def close(self):
        self.cancel_read()
        if self._loop and self._loop.is_running():
            try:
                self._run(self._disconnect(), timeout=5)
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread and self._loop_thread is not threading.current_thread():
                self._loop_thread.join(timeout=2)
        self.is_open = False

    async def _connect(self):
        from bleak import BleakClient, BleakScanner

        device = await BleakScanner.find_device_by_address(
            self.address,
            timeout=min(self._connect_timeout, 10),
        )
        if device is None:
            raise RuntimeError("PingPong BLE device is no longer advertising.")
        self._client = BleakClient(
            device,
            disconnected_callback=self._on_disconnected,
            timeout=self._connect_timeout,
        )
        try:
            await self._client.connect()
            await asyncio.wait_for(
                self._client.start_notify(self.RX_UUID, self._on_notification),
                timeout=10,
            )
        except Exception:
            if self._client.is_connected:
                await self._client.disconnect()
            raise
        self.is_open = True
        with self._read_condition:
            self._read_buffer.clear()
            self._read_condition.notify_all()

    async def _write(self, data):
        for offset in range(0, len(data), self.WRITE_CHUNK_SIZE):
            chunk = data[offset:offset + self.WRITE_CHUNK_SIZE]
            await self._client.write_gatt_char(self.TX_UUID, chunk, response=False)

    async def _disconnect(self):
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(self.RX_UUID)
            except Exception:
                pass
            await self._client.disconnect()
        self.is_open = False

    def _on_notification(self, _sender, data):
        with self._read_condition:
            self._read_buffer.extend(data)
            self._read_condition.notify_all()

    def _on_disconnected(self, _client):
        self.is_open = False
        with self._read_condition:
            self._read_condition.notify_all()

    def _start_loop(self):
        if self._loop and self._loop.is_running():
            return
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
        self._loop.close()

    def _run(self, coroutine, timeout):
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=timeout)
        except Exception:
            future.cancel()
            raise
