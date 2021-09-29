from dataclasses import dataclass
from typing import List
from datetime import datetime

from socketio import AsyncServer
from copy import deepcopy

from .TankObject import TankObject
from .vector import Vector


@dataclass
class PlayerInfo:
    id: str
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
    x: float = 0
    y: float = 0

    def to_json(self):
        dictionary = {key: value for key, value in self.__dict__.items() if key not in ('target', 'tank')}
        dictionary['target'] = {'x': self.target.x,
                                'y': self.target.y}
        return dictionary


    @staticmethod
    def from_dict(dictionary, tanks):
        dictionary['target'] = Vector(dictionary['target']['x'], dictionary['target']['y'])
        return PlayerInfo(**dictionary)

    async def emit_changes(self, tanks, server: AsyncServer, *args, **kwargs):
        await server.emit('update',
                          {'id': self.id,
                           'name': self.name,
                           **(tanks[self.id].get_changes())},
                          *args, **kwargs)

    async def emit_initial(self, tanks, server: AsyncServer, *args, **kwargs):
        await server.emit('initial',
                          {'id': self.id,
                           'name': self.name,
                           **(tanks[self.id].get_changes())},
                          *args, **kwargs)
