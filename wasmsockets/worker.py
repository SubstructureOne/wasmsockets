import js


def createworker(workerfunc: str):
    src = f'({workerfunc})()'
    blob = js.Blob.new([src], {'type': 'application/javascript'})
    url = js.URL.createObjectURL(blob)
    return js.Worker.new(url)


def websockets_worker(url):
    func = """
        () => {
            // will be initialized by WebWorker.postMessage
            self.sync = null
            self.buffer = null
            function connect() {
                return new Promise((resolve, reject) => {
                    let socket = new WebSocket('WEBSOCKET_ADDR')
                    socket.onopen = () => { resolve(socket) }
                    socket.onmessage = e => {
                        Atomics.wait(self.sync, 0, 1)
                        self.sync[1] = e.data.length
                        const encoded = new TextEncoder().encode(e.data)
                        for (let ind = 0; ind < e.data.length; ind += 1) {
                            self.buffer[ind] = encoded[ind]
                        }
                        Atomics.store(self.sync, 0, 1)
                        Atomics.notify(self.sync, 0, 1)
                    }
                })
            }
            self.socket_promise = connect()
            self.onmessage = msg => {
                self.receiving_port = msg.data.receiving_port
                self.buffer = msg.data.buffer
                self.sync = msg.data.sync
                self.receiving_port.onmessage = async e => {
                    const websocket = await self.socket_promise
                    console.log(`Sending ${e.data} over websocket`)
                    websocket.send(e.data)
                }
            }
        }
    """
    return createworker(func.replace("WEBSOCKET_ADDR", url))


class SynchronousIOProxy:
    """Provides the ability to synchronously communicate via WebSockets"""
    def __init__(self, sync, buffer, sending_port):
        """
        :param sync: An Int32Array based on a SharedArrayBuffer
        :param buffer: A Uint8Array based on a SharedArrayBuffer
        :param sending_port: A MessageChannel port for sending messages
        """
        self._sync = sync
        self._buffer = buffer
        self._sending_port = sending_port

    def send_message(self, message):
        self._sending_port.postMessage(message)

    def receive_message(self):
        # wait for a message to be ready
        js.Atomics.wait(self._sync, 0, 0)
        length = self._sync[1]
        message = list(self._buffer.to_py()[:length])
        js.Atomics.store(self._sync, 0, 0)
        js.Atomics.notify(self._sync, 0, 1)
        return message
