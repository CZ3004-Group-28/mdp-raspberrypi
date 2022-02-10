import json
import os
import socket
from typing import Optional

import bluetooth

from communication.communicator import Link
from logger import prepare_logger


class AndroidMessage:
    """
    Represents an outgoing Android message
    cat: [info, error, location]
    """
    def __init__(self, **kwargs):
        self._cat = kwargs.get('cat')
        self._value = kwargs.get('value')

    @property
    def cat(self):
        return self._cat

    @property
    def value(self):
        return self._value

    @property
    def jsonify(self) -> str:
        return json.dumps({'cat': self._cat, 'value': self._value})


class AndroidLink(Link):
    def __init__(self):
        super().__init__()
        self.server_sock = None
        self.client_sock = None

    def connect(self):
        try:
            # set discoverable in order for service to be advertisable
            os.system("hciconfig hci0 piscan")

            # initialize server socket
            self.server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.server_sock.bind(("", bluetooth.PORT_ANY))
            self.server_sock.listen(1)

            # parameters
            port = self.server_sock.getsockname()[1]
            uuid = '94f39d29-7d6d-437d-973b-fba39e49d4ee'

            # advertise
            bluetooth.advertise_service(self.server_sock, "RPi-Grp28", service_id=uuid,
                                        service_classes=[uuid, bluetooth.SERIAL_PORT_CLASS],
                                        profiles=[bluetooth.SERIAL_PORT_PROFILE])

            self.logger.info(f"Waiting for bluetooth connection on RFCOMM CHANNEL {port}...")
            self.client_sock, client_info = self.server_sock.accept()
            self.logger.info(f"Accepted connection from: {client_info}")

        except Exception as e:
            self.logger.error(f"Error in bluetooth link connection: {e}")
            self.server_sock.close()
            self.client_sock.close()

    def disconnect(self):
        try:
            self.logger.info("Disconnecting bluetooth link")
            self.server_sock.shutdown(socket.SHUT_RDWR)
            self.client_sock.shutdown(socket.SHUT_RDWR)
            self.client_sock.close()
            self.server_sock.close()
            self.client_sock = None
            self.server_sock = None
            self.logger.info("Disconnected bluetooth link")
        except Exception as e:
            self.logger.error(f"Failed to disconnect bluetooth link: {e}")
            exit()

    # todo: broken pipe error when trying to send messages after re-connection
    def send(self, message: AndroidMessage):
        try:
            self.client_sock.send(f"{message.jsonify}\n".encode("utf-8"))
            self.logger.debug(f"Sent to Android: {message.jsonify}")
        except OSError as e:
            self.logger.error(f"Error sending message to android: {e}")
            self.disconnect()
            self.connect()  # try to reconnect
            self.send(message)  # retry sending

    def recv(self) -> Optional[str]:
        try:
            message = self.client_sock.recv(1024).strip().decode("utf-8")
            self.logger.debug(f"Received from Android: {message}")
            return message
        except OSError as e:  # connection broken, try to reconnect
            self.logger.error(f"Error receiving message from android: {e}")
            self.disconnect()
            self.connect()
        return None
