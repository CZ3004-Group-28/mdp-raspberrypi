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


class Message:
    def __init__(self, **kwargs):
        self._destination = kwargs.get('destination')
        self._payload = kwargs.get('payload')

    @property
    def destination(self):
        return self._destination

    @destination.setter
    def destination(self, value):
        self._destination = value

    @property
    def payload(self):
        return self._payload

    @payload.setter
    def payload(self, value):
        self._payload = value


class AndroidMessage(Message):
    def __init__(self, **kwargs):
        super(AndroidMessage, self).__init__(**kwargs)
        self.type = kwargs.get('type')

    @property
    def json_str(self):
        return json.dumps({'type': self.type, 'msg': self.payload})
