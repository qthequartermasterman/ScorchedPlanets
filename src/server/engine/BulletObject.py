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
        self.destroys_terrain: bool = True
        self.generates_terrain: bool = False
        self.explosion_radius: float = 50
        self.collision_radius: float = 1
        self.explosion_sprite: SpriteType = SpriteType.EXPLOSION1_SPRITE
        self.explosion_sound: SoundType = SoundType.EXPLOSION7_SOUND
        self.bounces: int = 0  # Bounces for bouncing bullet (BULLET7)
        self.times_shot: int = 0  # Times shot manually by player after shooting initial bullet (BULLET8)
        self.bounce_limit: int = 0 # Max number of bounces
        self.teleporter: bool = False  # Does this bullet teleport the owner?
        self.creates_wormholes: bool = False  # Does this bullet generate a wormhole?

        # Set the damage, explosion radius, and/or other attributes based on the bullet type
        if sprite_type == SpriteType.BULLET_SPRITE:  # black standard
            self.damage = 10
            self.explosion_radius = 50
        elif sprite_type == SpriteType.BULLET2_SPRITE:  # red - dirt
            self.damage = 10
            self.explosion_radius = 50
            self.generates_terrain = True
            self.destroys_terrain = False
        elif sprite_type == SpriteType.BULLET4_SPRITE:  # grey egg shaped - splits in to 3
            self.damage = 7.5
            self.explosion_radius = 50
            self.collision_radius = .75
            self.time_to_live = 1.25
        elif sprite_type == SpriteType.BULLET5_SPRITE:  # green/red missile - large explosion radius
            self.damage = 12.5
            self.explosion_radius = 160
            self.collision_radius = .25
        elif sprite_type == SpriteType.BULLET6_SPRITE:  # green/grey missile- timed explosion
            self.damage = 10
            self.explosion_radius = 100
            self.time_to_live = 6.0
        elif sprite_type == SpriteType.BULLET7_SPRITE:  # yellow rounded square - bounces off planets
            self.damage = 7.5
            self.explosion_radius = 50
            self.collision_radius = .75
            self.bounce_limit = 2
        elif sprite_type == SpriteType.BULLET3_SPRITE:  # grey rounded square - teleportation bullet
            self.damage = 0
            self.explosion_radius = 0
            self.collision_radius = .75
            self.teleporter = True
        elif sprite_type == SpriteType.BULLET8_SPRITE:  # yellow egg - shoots bullets when right click
            self.damage = 7.5
            self.explosion_radius = 50
            self.collision_radius = .75
        elif sprite_type == SpriteType.BULLET9_SPRITE:  # pointy grey bullet - accelerates until it hits something
            self.damage = 28
            self.explosion_radius = 25
            self.collision_radius = .1
            self.acceleration = self.velocity
        elif sprite_type == SpriteType.BULLET10_SPRITE:  # long grey&brown bullet - explode in air when right click
            self.damage = 7.5
            self.explosion_radius = 100
            self.collision_radius = .1
        elif sprite_type == SpriteType.BULLET11_SPRITE:  # short red & grey bullet - "fatman"
            self.damage = 35
            self.explosion_radius = 225
            self.collision_radius = .1
            self.explosion_sound = SoundType.EXPLOSION3_SOUND
        elif sprite_type == SpriteType.BULLET12_SPRITE:  # black cannon ball - creates a pair of wormholes
            self.damage = 2.5
            self.explosion_radius = 5
            self.collision_radius = .1
            self.creates_wormholes = True
        elif sprite_type == SpriteType.MINE_SPRITE:
            self.damage = 12.5
            self.explosion_radius = 120
            self.collision_radius = .75

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
