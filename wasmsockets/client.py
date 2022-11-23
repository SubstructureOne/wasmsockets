# This module is expected to be used in a Pyodide environment, in which the
# "js" and "pyodide" packages are provided.
from asyncio import Queue

import js
import pyodide.ffi


def connect(uri):
    return WasmSocket(uri)


class WasmSocket:
    def __init__(self, uri):
        self._uri = uri
        self._socket = js.WebSocket.new(uri)
        self._socket.addEventListener('open', pyodide.ffi.create_proxy(self._open_handler))
        self._socket.addEventListener('message', pyodide.ffi.create_proxy(self._message_handler))
        self._socket.addEventListener('error', pyodide.ffi.create_proxy(self._error_handler))
        self._incoming = Queue()

    async def send(self, message: bytes):
        self._socket.send(message)

    async def recv(self):
        return await self._incoming.get()

    async def _open_handler(self, event):
        js.console.log(f"Open event: {event.data}")

    async def _message_handler(self, event):
        js.console.log(f"Message event: {event.data}")
        await self._incoming.put(event.data)

    async def _error_handler(self, event):
        js.console.log(f"Error event: {event.data}")
