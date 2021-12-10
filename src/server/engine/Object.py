from math import cos, sin
from random import random, choice
from typing import Union

from socketio import AsyncServer

from .SoundType import SoundType
from .SpriteType import SpriteType
from .vector import Vector, Sphere
from .util import colors


class Object:
    def __init__(self, position: Vector, sprite_type: SpriteType = None):
        """

        :param position: Vector representing position
        """

        self.id = id(self)

        self.sprite_type: SpriteType = sprite_type

        self.position: Vector = position  # Current position
        self.old_position: Vector = position  # Position on the previous time step
        self.mass: float = 0
        self.rotation_speed: float = 0
        self.roll: float = 0  # the current rotation of the object in radians
        self.velocity: Vector = Vector(0, 0)
        self.acceleration: Vector = Vector(0, 0)

        self.affected_by_gravity: bool = False
        # Initial total mechanical energy of the object. -1 means that the energy was never calculated. Used for
        # debugging physics precision.
        self.old_energy: float = -1
        self.collision_radius: float = 0
        # self._collision_sphere: Sphere = Sphere(self.position, self.collision_radius)

        self.gun_timer: float = 0
        self.smoke_timer: float = 0
        self.hue = choice(colors)
        # self.smoke_color

        self.dead: bool = False

        self.strafe_left: bool = False
        self.strafe_right: bool = False

        self.is_bullet: bool = False

        # queued changes to send via the socket
        # self.changes_queue = Queue()
        self.changes_queue = []

        # Send a sound in the next update?
        self._need_to_emit_sound: bool = False
        self.sound_type_to_emit: Union[SoundType, ''] = ''

    @property
    def collision_sphere(self) -> Sphere:
        return Sphere(self.position, self.collision_radius)

    @property
    def speed(self):
        return abs(self.velocity)

    def move(self):
        self.old_position = self.position
        # Get the elapsed seconds since the previous time step. We're just setting this as a constant for right now.
        dt = .1

        # Calculate effect of gravity for all gravitationally affected objects
        # TODO: If there is only one source of gravity, instead just predict its conic section orbit

        #  Having the objects move AFTER calculating what their velocity should be on the next time step seems to
        #  improve numerical stability of simulations. This makes a certain amount of sense. This effectively is a crude
        #  Semi-implicit Euler integration, as opposed to the naive Euler integration it was doing before. It's still
        #  not 100% accurate, but at least in 2 body systems, elliptical orbits stay elliptical and do not precess
        #  (rotate) as quickly as they were before! I'll take the appearance of accuracy over blatant inaccuracy.

        # Improved accuracy could probably be found in doing a Runge Kutta integration, but that's way more work than
        # I want to commit today.
        self.velocity += self.acceleration * dt
        self.position += self.velocity * dt
        self.collision_sphere.center = self.position

    def collision_response(self):
        self.old_position = self.position

    def collision_reflection_response(self, unit_normal: Vector):
        """
        Instead of stopping the object, it reflects the object following Snell's law.
        :param unit_normal: Unit vector that is normal to the surface against which we collide
        :return:
        """
        assert abs(unit_normal) == 1
        self.velocity = self.velocity - 2 * (self.velocity * unit_normal) * unit_normal

    @property
    def view_vector(self):
        return Vector(-sin(self.roll), cos(self.roll))

    def emit_smoke(self):
        pass

    def death_fx(self):
        pass

    def kill(self):
        self.dead = True
        self.death_fx()

    async def emit_initial(self, server: AsyncServer, *args, **kwargs) -> None:
        """
        Send all initial properties of this object to the server
        :param server: AsyncServer to send changes from via socket-io protocol
        :return: None
        """
        await server.emit('initial',
                          {'id': self.id,
                           'sprite': str(self.sprite_type),
                           'hue': self.hue,
                           'x': self.position.x,
                           'y': self.position.y}, *args, **kwargs)

    async def emit_changes(self, server: AsyncServer, *args, **kwargs) -> None:
        """
        Send all changes of this object to the server
        :param server: AsyncServer to send changes from via socket-io protocol
        :return: None
        """
        # while not self.changes_queue.empty():
        #     item = self.changes_queue.get()
        #     await server.emit('update',
        #                       {'id': self.id,
        #                        'sprite': str(self.sprite_type),
        #                        'update': item}, *args, **kwargs)
        #     self.changes_queue.task_done()
        if len(self.changes_queue):
            await server.emit('update',
                              {'id': self.id,
                               'sprite': str(self.sprite_type),
                               'update': self.changes_queue}, *args, **kwargs)
        self.changes_queue = []

    @property
    def need_to_emit_sound(self) -> bool:
        """
        Check if a sound needs to be emitted. Returns True if so, False otherwise. Side effect so that once this
        method is called, the private variable self._need_to_emit_sound becomes False, to signal that the sound has
        already been emitted.
        :return: bool if sound needs to be emitted.
        """
        emit_sound_bool = self._need_to_emit_sound
        self._need_to_emit_sound = False
        return emit_sound_bool

    @property
    def sound_type_to_play(self) -> Union[SoundType, str]:
        """
        :return: SoundType of the sound if needs to be emitted, else ''
        """
        return self.sound_type_to_emit if self.need_to_emit_sound else ''

    def play_sound(self, sound_type: SoundType) -> None:
        """
        Mark a sound that needs to be emitted.
        :param sound_type: SoundType that needs to be emitted
        :return: None
        """
        # print(f'{id(self), type(self)} is playing sound {sound_type}')
        self._need_to_emit_sound = True
        self.sound_type_to_emit = sound_type
