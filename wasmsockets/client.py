# This module is expected to be used in a Pyodide environment, in which the
# "js" and "pyodide" packages are provided.
from asyncio import Queue, Event

import js
import pyodide.ffi


def connect(uri):
    return WasmSocket(uri)


class WasmSocket:
    def __init__(self, uri):
        self._uri = uri
        socket = js.WebSocket.new(uri)
        socket.binaryType = "arraybuffer"
        socket.addEventListener('open', pyodide.ffi.create_proxy(self._open_handler))
        socket.addEventListener('message', pyodide.ffi.create_proxy(self._message_handler))
        socket.addEventListener('error', pyodide.ffi.create_proxy(self._error_handler))
        self._socket = socket
        self._incoming = Queue()
        self._isopen = Event()

    async def send(self, message: bytes):
        js.console.log(f"Sending message: {message}; checking for socket open")
        await self._isopen.wait()
        js.console.log(f"Socket now open; sending")
        self._socket.send(message)

    async def recv(self):
        js.console.log(f"Receiving message; checking for socket open")
        await self._isopen.wait()
        js.console.log(f"Waiting to receive message...")
        result = await self._incoming.get()
        js.console.log(f"Message received: {result}")
        return result

    async def _open_handler(self, event):
        js.console.log(f"Open event: {event.to_py()}")
        self._isopen.set()

    async def _message_handler(self, event):
        js.console.log(f"Message event: {event.data}")
        await self._incoming.put(event.data)

    async def _error_handler(self, event):
        js.console.log(f"Error event: {event}")
