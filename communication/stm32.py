from typing import Optional

import serial
from communication.communicator import Link
from settings import SERIAL_PORT, BAUD_RATE


# todo: STMLink for communicating with the STM board
class STMLink(Link):
    def __init__(self):
        self.serial_link = None

    def connect(self):
        self.serial_link = serial.Serial(SERIAL_PORT, BAUD_RATE)

    def disconnect(self):
        self.serial_link.close()
        self.serial_link = None

    def send(self, message: str) -> None:
        self.serial_link.writelines([message])

    def recv(self) -> Optional[str]:
        # todo: check possible values for message
        message = self.serial_link.readline()
        return message
