from dataclasses import dataclass
from typing import List
from datetime import datetime
from .vector import Vector


@dataclass
class PlayerInfo:
    id: str
    x: float
    y: float
    w: int
    h: int
    hue: int
    type: str
    lastHeartbeat: float  # Unix timestamp
    target: Vector
    name: str = 'Unnamed'
    screenWidth: int = 0
    screenHeight: int = 0
    admin: bool = False

    def to_json(self):
        dictionary = self.__dict__
        dictionary['target'] = {'x': self.target.x,
                                'y': self.target.y}
        return dictionary


    @staticmethod
    def from_dict(dictionary):
        dictionary['target'] = Vector(dictionary['target']['x'], dictionary['target']['y'])
        return PlayerInfo(**dictionary)
