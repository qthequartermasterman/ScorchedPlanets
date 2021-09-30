import datetime
from random import random
from typing import List

from socketio import AsyncServer

from .Object import Object
from .PlanetObject import PlanetObject
from .SpriteType import SpriteType
from .vector import Vector, UnitVector
from .Config import turns_enabled, gravity_constant
from .SoundType import SoundType
from . import Common

from enum import Enum, auto
from math import sqrt, pi


class TankState(Enum):
    Manual = auto()
    Move = auto()
    MoveLeft = auto()
    MoveRight = auto()
    Aim = auto()
    AimLeft = auto()
    AimRight = auto()
    Power = auto()
    PowerUp = auto()
    PowerDown = auto()
    Fire = auto()
    Wait = auto()
    Think = auto()
    PostFire = auto()
    Dead = auto()


class TankAnimationState(Enum):
    Normal = auto()
    Falling = auto()


class TankObject(Object):
    def __init__(self, longitude: float, planet: PlanetObject, color: str = None, angle: float = 0):
        super().__init__(Vector(0, 0), sprite_type=SpriteType.GREY1_SPRITE)
        self.home_planet = planet
        self.longitude = longitude
        self.angle: float = angle  # Angle at which the turret gun is pointing
        self.health_points = 100  # Starting health

        self.damage_sound = SoundType.EXPLOSION1_SOUND
        self.animation_state = TankAnimationState.Normal  # Tells the renderer which animation state we should render.

        # Get starting location
        planet_center = planet.position
        direction = UnitVector(longitude)
        altitude = planet.get_altitude_at_angle(longitude)
        self.position = planet_center + (altitude + self.collision_radius) * direction

        # AI private variables
        self.is_player_character: bool = False
        self.accuracy_multiplier: float = 15.0
        self.current_state: TankState = TankState.Wait
        self.desired_angle: float = 45
        # +1 to keep adjusting angle in the pos direction, -1 to adjust in the neg direction, 0 to not change at all.
        self.desired_angle_direction: int = 1
        self.desired_power: float
        # +1 to keep adjusting power in the pos direction, -1 to adjust in the neg direction, 0 to not change at all.
        desired_power_direction: int = 1
        self.desired_angle_relative_to_planet: float
        # +1 to keep adjusting angle_relative_to_planet in the pos direction, -1 to adjust in the neg direction,
        # 0 to not change at all.
        self.desired_angle_relative_to_planet_direction: int = 0
        self.previous_distance: float = 0

        # variables for pausing after turn
        self.paused_after_hit: bool = False
        self.time_hit: float = 0
        self.transStarted: bool = False
        self.playerNumber: int = 0

        # variables for bullet selection
        self.selected_bullet: int = 0
        # Array of available bullet types to choose from
        self.bullet_types: List[SpriteType] = [SpriteType.BULLET_SPRITE, SpriteType.BULLET2_SPRITE,
                                               SpriteType.BULLET4_SPRITE, SpriteType.BULLET5_SPRITE,
                                               SpriteType.BULLET7_SPRITE, SpriteType.BULLET6_SPRITE,
                                               SpriteType.BULLET3_SPRITE, SpriteType.BULLET8_SPRITE,
                                               SpriteType.BULLET9_SPRITE, SpriteType.BULLET10_SPRITE,
                                               SpriteType.BULLET11_SPRITE, SpriteType.BULLET12_SPRITE,
                                               SpriteType.MINE_SPRITE]
        # Amount of bullets of each type left to fire
        self.bullet_counts: List[int] = [9999, 9999, 5, 5, 5, 5, 5, 5, 5, 5, 1, 2, 2]
        # Total number of types of bullets this tank has access to
        self.bullet_type_count: int = 13

        # Moving/shooting limits
        self.maxFuel: float = 500  # maximum amount of fuel the tank has for moving
        self.currentFuel: float = self.maxFuel  # when this reaches 0, the player cannot move anymore
        # the maximum power the player can shoot at. leftover currentFuel is added onto this amount
        self.basePower: float = 700
        self.lastFiredShot: float  # time of last fired shot

        # Internal AI State parameters
        # Velocity of a circular orbit is sqrt(G*M/R). Initial power should be a circular orbit to make life easier
        # Power == initial velocity
        self.power = sqrt(gravity_constant * planet.mass / planet.get_altitude_at_angle(longitude))
        self.desired_power = self.power
        self.desired_longitude = self.longitude
        self.power_speed: float = 0  # Speed at which to increase or decrease power.
        self.in_control: bool  # If input is currently controlling this object

        if color:
            self.hue = color

    def fire_gun(self, bullet: SpriteType) -> None:
        """
        Create a bullet object and a flash particle effect.
        It is assumed that the object is round and that the bullet
        appears at the edge of the object in the direction
        that it is facing and continues moving in that direction.
        :param bullet: sprite type of the bullet
        :return:
        """

        if self.dead:  # We don't want to shoot if we're supposed to be dead.
            return
        # TODO: Play audio

        view: Vector = self.view_vector
        pos: Vector = self.position

        # Set camera and control lock

        if turns_enabled:
            Common.control_lock = True
            Common.camera_mode = Common.CameraMode.BULLET_LOCKED

        bullet = Common.object_manager.create_bullet(bullet, pos, self.hue)
        bullet.owner = self

        norm: Vector = Vector(view.y, -view.x)  # normal to direction
        m: float = 2 * random() - 1
        deflection = Vector(0, 0)

        bullet.velocity = self.power * (view + deflection)  # Power is the starting velocity
        bullet.roll = self.roll

        if self.selected_bullet not in (0, 1):
            self.bullet_counts[self.selected_bullet] -= 1
        while not self.bullet_counts[self.selected_bullet]:
            self.next_bullet_type()

        self.gun_timer = datetime.datetime.now().timestamp()

        # TODO: Gunfire particle effect on client side

    def fire_phantom_gun(self, bullet: SpriteType, orientation: Vector, power: float,
                         position: Vector = Vector(0, 0)) -> float:
        if position == Vector(0, 0):  # In the default case, use the current position
            position = self.position
        position = position + .5 * self.collision_radius * orientation
        power = self.power

        # to get better results, we should average this over a couple shots with adjusted angles/power.
        # The physics simulations will mess us up quite frequently.
        num_simulations: int = 3
        running_distance_sum: float = 0
        for i in range(num_simulations):
            if i:
                power /= 1.01
                velocity = self.velocity + power * orientation  # Power is the starting velocity
                running_distance_sum += Common.object_manager.create_phantom_bullet(bullet, position, velocity, self)
        return running_distance_sum / num_simulations

    def take_damage(self, damage: int):
        """
        Decrease the health points by damage. Returns the current health point after damage is taken. Kills the tank
        if damage is less than 0.
        :param damage: is the number of hp to reduce.
        :return: the number of health_points after taking damage.
        """
        # The volume with which we will play the "OW" sound. It'll be loud if it does more relative damage.
        volume = damage / self.health_points
        self.health_points -= damage
        if self.health_points <= 0:
            self.current_state = TankState.dead
            self.kill()
        # TODO: Play audio
        return self.health_points

    def teleport(self, pos: Vector, new_planet: PlanetObject):
        self.home_planet = new_planet
        self.position = pos

    def move(self):
        # Check if I'm dead
        if self.health_points <= 0:
            self.kill()
        t: float = .1  # Time step

        self.power += self.power_speed * t  # Affect power if keys are pressed down.
        # It's totally possible to bring the power to the negatives, meaning the projectile starts shooting backwards.
        # Let's not do that.
        self.power = max(0, self.power)
        self.angle += 30 * self.rotation_speed * t  # We want to move 30 degrees every second
        self.angle = self.angle % 360  # Make sure our angle is less than 360.
        self.roll = pi + (self.angle + self.longitude) * pi / 180
        viewvec: Vector = self.view_vector
        delta: float = 40 * t

        if self.strafe_left:
            self.longitude -= delta
        elif self.strafe_right:
            self.longitude += delta
        self.longitude = self.longitude % 360

        planet_center: Vector = self.home_planet.position
        direction_unit_vector: Vector = UnitVector(self.longitude * pi / 180)
        altitude: int = self.home_planet.get_altitude_at_angle(self.longitude)
        desired_pos: Vector = planet_center + (altitude * self.collision_radius) * direction_unit_vector
        current_altitude: float = abs(self.position - planet_center)

        if current_altitude - altitude - self.collision_radius > 10 and not self.strafe_left and not self.strafe_right:
            # We are currently more than 10 units higher than where we should be, and we're not currently moving
            # In that case, we should do a falling animation.
            self.animation_state = TankAnimationState.Falling
            self.position = planet_center + (current_altitude - 3) * direction_unit_vector  # Move 1 unit down
        else:
            # No animation, just jump to proper spot
            self.animation_state = TankAnimationState.Normal
            self.position = planet_center + (altitude + self.collision_radius) * direction_unit_vector

        self.strafe_right = self.strafe_left = False
        self.collision_sphere.center = self.position

    def next_bullet_type(self) -> SpriteType:
        """
        Go to next bullet type, go to first one if at end
        :return: SpriteType of the bullet sprite
        """
        self.selected_bullet += 1
        if self.selected_bullet >= self.bullet_type_count:
            self.selected_bullet = 0
        while not self.bullet_counts[self.selected_bullet]:  # If that's empty, then switch to the next bullet type
            self.next_bullet_type()

        return self.bullet_types[self.selected_bullet]

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
                           'y': self.position.y,
                           'planet_x': self.home_planet.position.x,
                           'planet_y': self.home_planet.position.y,
                           'angle': self.angle,
                           'longitude': self.longitude
                           },
                          *args, **kwargs)

    async def emit_changes(self, server: AsyncServer, *args, **kwargs) -> None:
        """
        Send all changes of this object to the server
        :param server: AsyncServer to send changes from via socket-io protocol
        :return: None
        """
        while not self.changes_queue.empty():
            item = self.changes_queue.get()
            await server.emit('update',
                              {'id': self.id,
                               'sprite': str(self.sprite_type),
                               'x': self.position.x,
                               'y': self.position.y,
                               'planet_x': self.home_planet.position.x,
                               'planet_y': self.home_planet.position.y,
                               'angle': self.angle,
                               'longitude': self.longitude,
                               'update': item}, *args, **kwargs)
            self.changes_queue.task_done()

    def get_changes(self):
        return {'sprite': str(self.sprite_type),
                'x': self.position.x,
                'y': self.position.y,
                'planet_x': self.home_planet.position.x,
                'planet_y': self.home_planet.position.y,
                'angle': self.angle,
                'longitude': self.longitude, }

    def think(self):
        pass
