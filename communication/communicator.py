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

    @property
    def json(self):
        return json.dumps({'destination': self._destination, 'payload': self._payload}) + "\r\n"

    def load_json(self, json_str: str):
        # set instance attributes using json representation of a Message
        message = json.loads(json_str)
        self._destination = message['destination']
        self._payload = message['payload']
