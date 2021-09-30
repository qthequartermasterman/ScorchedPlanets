from datetime import datetime
from math import atan2

from socketio import AsyncServer

from .Object import Object
from .SoundType import SoundType
from .SpriteType import SpriteType
from .vector import Vector


class BulletObject(Object):
    def __init__(self, position: Vector, sprite_type: SpriteType = None, trail_color: str = ''):
        super().__init__(position, sprite_type)
        self.hue: str = trail_color
        self.is_phantom: bool = False
        self.owner = None
        self.is_bullet = True

        # Kills itself after this many seconds. -1 means it lives until it collides with something
        # Normally 30 seconds. Some bullets may defer. 5 seconds is too short for game play, but good for testing.
        self.time_to_live: float = 30
        self.time_created: float = datetime.now().timestamp()

        # Reactions stuff
        self.damage: int = 10
        self.explosion_radius: float = 0
        self.collision_radius: float = 10
        self.explosion_sprite: SpriteType = SpriteType.WATER_SPRITE
        self.explosion_sound: SoundType = SoundType.EXPLOSION7_SOUND
        self.bounces: float = 0  # Bounces for bouncing bullet (BULLET7)
        self.times_shot: int = 0  # Times shot manually by player after shooting initial bullet (BULLET8)

    def move(self):
        # print(self.time_created, datetime.now().timestamp())
        if datetime.now().timestamp() - self.time_created >= self.time_to_live != -1:
            self.kill()
            return

        # TODO: Implement special stuff like bouncing or whatever for certain bullet types

        Object.move(self)
        self.roll = atan2(self.velocity.y, self.velocity.x)
        if not self.is_phantom:
            self.EmitSmoke()

    async def emit_changes(self, server: AsyncServer, *args, **kwargs) -> None:
        """
        Send all changes of this object to the server
        :param server: AsyncServer to send changes from via socket-io protocol
        :return: None
        """
        await server.emit('update',
                          {'id': self.id,
                           'sprite': str(self.sprite_type),
                           'roll': self.roll,

                           'x': self.position.x,
                           'y': self.position.y},
                          *args, **kwargs)

    def get_json(self):
        return {'id': self.id,
                'sprite': str(self.sprite_type),
                'roll': self.roll,

                'x': self.position.x,
                'y': self.position.y}

    def EmitSmoke(self):
        pass
