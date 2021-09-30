from dataclasses import dataclass
from socketio import AsyncServer
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
        try:
            changes = {'id': self.id,
                       'name': self.name,
                       **(tanks[self.id].get_changes())}
            await server.emit('update', changes, *args, **kwargs)
        except KeyError:  # self.id not available in tanks, so the player must be dead.
            await server.emit('RIP', room=self.id)

    async def emit_initial(self, tanks, server: AsyncServer, *args, **kwargs):
        try:
            changes = {'id': self.id,
                       'name': self.name,
                       **(tanks[self.id].get_changes())}
            await server.emit('update', changes, *args, **kwargs)
        except KeyError:  # self.id not available in tanks, so the player must be dead.
            await server.emit('RIP', room=self.id)
