from typing import List

from .Object import Object
from .PlanetObject import PlanetObject
from .SpriteType import SpriteType
from .vector import Vector, UnitVector
from .Config import gravity_constant
from .SoundType import SoundType

from enum import Enum, auto
from math import sqrt


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
    def __init__(self, longitude: float, planet: PlanetObject, color: str = None):
        super().__init__(Vector(0, 0))
        self.home_planet = planet
        self.longitude = longitude
        self.angle: float = 0  # Angle at which the turret gun is pointing
        self.health_points = 100  # Starting health

        self.damage_sound = SoundType.EXPLOSION1_SOUND
        self.animation_state = TankAnimationState.Normal  # Tells the renderer which animation state we should render.

        # Get starting location
        planet_center = planet.position
        direction = UnitVector(longitude)
        altitude = planet.get_altitude_at_angle(longitude)
        self.position = planet_center + (altitude + self.collision_radius) * direction

        # AI private variables
        is_player_character: bool = False
        accuracy_multiplier: float = 15.0
        current_state: TankState = TankState.Wait
        desired_angle: float = 45
        # +1 to keep adjusting angle in the pos direction, -1 to adjust in the neg direction, 0 to not change at all.
        desired_angle_direction: int = 1
        desired_power: float
        # +1 to keep adjusting power in the pos direction, -1 to adjust in the neg direction, 0 to not change at all.
        desired_power_direction: int = 1
        desired_angle_relative_to_planet: float
        # +1 to keep adjusting angle_relative_to_planet in the pos direction, -1 to adjust in the neg direction,
        # 0 to not change at all.
        desired_angle_relative_to_planet_direction: int = 0
        previous_distance: float = 0

        # variables for pausing after turn
        paused_after_hit: bool = False
        time_hit: float = 0
        transStarted: bool = False
        playerNumber: int = 0

        # variables for bullet selection
        selected_bullet: int = 0
        # Array of avaiable bullet types to choose from
        bullet_types: List[SpriteType] = [SpriteType.BULLET_SPRITE, SpriteType.BULLET2_SPRITE,
                                          SpriteType.BULLET4_SPRITE, SpriteType.BULLET5_SPRITE,
                                          SpriteType.BULLET7_SPRITE, SpriteType.BULLET6_SPRITE,
                                          SpriteType.BULLET3_SPRITE, SpriteType.BULLET8_SPRITE,
                                          SpriteType.BULLET9_SPRITE, SpriteType.BULLET10_SPRITE,
                                          SpriteType.BULLET11_SPRITE, SpriteType.BULLET12_SPRITE,
                                          SpriteType.MINE_SPRITE]
        # Amount of bullets of each type left to fire
        bullet_counts: List[int] = [9999, 9999, 5, 5, 5, 5, 5, 5, 5, 5, 1, 2, 2]
        # Total number of types of bullets this tank has access to
        bullet_type_count: int = 13

        # Moving/shooting limits
        maxFuel: float = 500  # maximum amount of fuel the tank has for moving
        currentFuel: float = maxFuel  # when this reaches 0, the player cannot move anymore
        # the maximum power the player can shoot at. leftover currentFuel is added onto this amount
        basePower: float = 700
        lastFiredShot: float  # time of last fired shot

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

    def fire_gun(self, bullet: SpriteType):
        pass

    def fire_phantom_gun(self, bullet: SpriteType, orientation: Vector, power: float, position: Vector = Vector(0, 0)):
        pass

    def take_damage(self, damage: int):
        """
         Decrease the health points by damage. Returns the current health point after damage is taken. Kills the tank if damage is less than 0.
        :param damage: is the number of hp to reduce.
        :return: the number of health_points after taking damage.
        """
