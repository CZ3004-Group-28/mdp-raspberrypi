import json
from abc import ABC, abstractmethod
from typing import Optional


class Link(ABC):
    @abstractmethod
    def send(self, message: str) -> None:
        pass

    @abstractmethod
    def recv(self) -> Optional[str]:
        pass


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
    def jsonify(self):
        return json.dumps({'cat': self._cat, 'value': self._value})
