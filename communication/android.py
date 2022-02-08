import os
import socket
from typing import Optional

import bluetooth
from communication.communicator import Link, AndroidMessage


class AndroidLink(Link):
    def __init__(self):
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

            print(f"[-] Waiting for bluetooth connection on RFCOMM CHANNEL {port}...")
            self.client_sock, client_info = self.server_sock.accept()
            print("[✔] Accepted connection from", client_info)

        except Exception as e:
            print(e)
            self.server_sock.close()
            self.client_sock.close()

    def disconnect(self):
        try:
            print("[-] Disconnecting...")
            self.server_sock.shutdown(socket.SHUT_RDWR)
            self.client_sock.shutdown(socket.SHUT_RDWR)
            self.client_sock.close()
            self.server_sock.close()
            self.client_sock = None
            self.server_sock = None
            print("[✔] Disconnected")
        except Exception as e:
            print("Disconnecting failed", e)
            exit()

    # todo: broken pipe error when trying to send messages after re-connection
    def send(self, message: AndroidMessage):
        try:
            self.client_sock.send(f"{message.jsonify}\n".encode("utf-8"))
        except OSError as e:
            print("[!] Error sending message to android:", e)
            self.disconnect()
            self.connect()  # try to reconnect
            self.send(message)  # retry sending

    def recv(self) -> Optional[str]:
        try:
            message = self.client_sock.recv(1024).strip().decode("utf-8")
            return message
        except OSError as e:  # connection broken, try to reconnect
            print("[!] Error receiving message from android:", e)
            self.disconnect()
            self.connect()
        return None
