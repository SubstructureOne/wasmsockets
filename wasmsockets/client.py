import sys
from asyncio import Queue, Event
from typing import Any, Callable, Optional
from dataclasses import dataclass

BytesLike = bytes, bytearray, memoryview


def iswasm():
    return sys.platform == 'emscripten'


if iswasm():
    # These packages are only available in a Pyodide environment. They never
    # need to be installed separately. We will only reference them when we
    # detect we are running in WebAssembly.
    import js
    import pyodide.ffi
else:
    import websockets


async def connect(uri):
    socket = WasmSocket(uri)
    await socket.connect()
    return socket

@dataclass
class SabProxy:
    send: Callable[[Any], None]
    recv: Callable[[], Any]

SAB_PROXY: Optional[SabProxy] = None

def use_sab_proxy(send, recv):
    global SAB_PROXY
    SAB_PROXY = SabProxy(send, recv)


class WasmSocket:
    def __init__(self, uri):
        self._uri = uri
        # _jssocket or _pysockets only gets initialized when calling connect().
        # _jssocket will be initialized in a WebAssembly environment; _pysocket
        # will be initialized in a native environment.
        self._jssocket = None
        self._pysocket = None
        self._message_handlers = list()
        if iswasm():
            self._incoming = Queue()
            self._isopen = Event()
        else:
            self._incoming = None
            self._isopen = None

    async def connect(self):
        if iswasm():
            socket = js.WebSocket.new(self._uri)
            socket.binaryType = "arraybuffer"
            socket.addEventListener(
                'open',
                pyodide.ffi.create_proxy(self._open_handler)
            )
            socket.addEventListener(
                'message',
                pyodide.ffi.create_proxy(self._message_handler)
            )
            socket.addEventListener(
                'error',
                pyodide.ffi.create_proxy(self._error_handler)
            )
            self._jssocket = socket
        else:
            self._pysocket = await websockets.connect(self._uri)

    async def send(self, message):
        """Sends a message over the WebSocket.

        Sends a Binary frame if message is bytes-like; sends as a Text frame
        if message is a str.

        NOTE: while the native websockets library supports fragmentation via
        sending in an iterable, the WebAssembly version currently does not.
        Only pass in a str or a bytes-like object.
        """
        if iswasm():
            js.console.log(f"Sending message: {message}; checking for socket open")
            await self._isopen.wait()
            js.console.log(f"Socket now open; sending")
            if isinstance(message, BytesLike):
                data = pyodide.ffi.to_js(message)
            else:
                data = message
            self._jssocket.send(data)
        else:
            await self._pysocket.send(message)

    def send_sync(self, message):
        if SAB_PROXY is None:
            raise NotImplementedError("Sync methods only supported when using the SharedArrayBuffer proxy")
        if isinstance(message, BytesLike):
            data = pyodide.ffi.to_js(message)
        else:
            data = message
            SAB_PROXY.send(data)

    async def recv(self):
        if iswasm():
            js.console.log(f"Receiving message; checking for socket open")
            await self._isopen.wait()
            js.console.log(f"Waiting to receive message...")
            result = await self._incoming.get()
            js.console.log(f"Message received: {result}")
        else:
            result = await self._pysocket.recv()
        return result

    def recv_sync(self):
        if SAB_PROXY is None:
            raise NotImplementedError("Sync methods only supported when using the SharedArrayBuffer proxy")
        return SAB_PROXY.recv()

    async def close(self):
        if iswasm():
            self._jssocket.close()
        else:
            await self._pysocket.close()

    def add_handlers(self, message_handler, wait_handler):
        # When running in a WASM environment, we may want/need to synchronously
        # wait for a message to be received. This is complicated because if we
        # block the main thread of execution, we can't receive any messsages,
        # so we'll never unblock. Therefore we need to pass off the handling of
        # receiving message to another worker.
        pass

    # JS callback handlers

    async def _open_handler(self, event):
        js.console.log(f"Open event: {event.to_py()}")
        self._isopen.set()

    async def _message_handler(self, event):
        js.console.log(f"Message event: {event.data}")
        await self._incoming.put(event.data)

    async def _error_handler(self, event):
        js.console.log(f"Error event: {event}")
