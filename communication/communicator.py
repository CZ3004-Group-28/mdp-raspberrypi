from abc import ABC, abstractmethod
from typing import Optional

from logger import prepare_logger


class Link(ABC):
    def __init__(self):
        self.logger = prepare_logger()

    @abstractmethod
    def send(self, message: str) -> None:
        pass

    @abstractmethod
    def recv(self) -> Optional[str]:
        pass
