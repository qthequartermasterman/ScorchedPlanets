from .Object import Object
from .PlanetObject import PlanetObject
from .vector import Vector, UnitVector
from .Config import gravity_constant

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

        # Get starting location
        planet_center = planet.position
        direction = UnitVector(longitude)
        altitude = planet.get_altitude_at_angle(longitude)
        self.position = planet_center + (altitude + self.collision_radius) * direction

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
