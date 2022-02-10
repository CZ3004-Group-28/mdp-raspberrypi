from typing import Optional

import serial
from communication.communicator import Link
from settings import SERIAL_PORT, BAUD_RATE


class STMLink(Link):
    def __init__(self):
        super().__init__()
        self.serial_link = None

    def connect(self):
        self.serial_link = serial.Serial(SERIAL_PORT, BAUD_RATE)
        self.logger.info("Connected to STM32")

    def disconnect(self):
        self.serial_link.close()
        self.serial_link = None
        self.logger.info("Disconnected from STM32")

    def send(self, message: str) -> None:
        self.serial_link.write(f"{message}\n".encode("utf-8"))
        self.logger.debug(f"Sent to STM32: {message}")

    def recv(self) -> Optional[str]:
        # todo: check possible values for message
        message = self.serial_link.readline().strip().decode("utf-8")
        self.logger.debug(f"Received from STM32: {message}")
        return message
