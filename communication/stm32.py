from typing import Optional

from communication.communicator import Link


# todo: STMLink for communicating with the STM board
class STMLink(Link):
    def send(self, message: str) -> None:
        pass

    def recv(self) -> Optional[str]:
        pass
