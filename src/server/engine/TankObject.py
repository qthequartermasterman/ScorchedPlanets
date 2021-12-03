import datetime
from enum import Enum, auto
from math import sqrt, pi
from random import randint
from typing import List

from socketio import AsyncServer

from .Config import turns_enabled, gravity_constant
from .Object import Object
from .PlanetObject import PlanetObject
from .SoundType import SoundType
from .SpriteType import SpriteType
from .vector import Vector, UnitVector


class TankState(Enum):
    """All the possible states that a tank could be in."""
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
    FireWait = auto()
    Wait = auto()
    Think = auto()
    PostFire = auto()
    Dead = auto()


class TankAnimationState(Enum):
    """All of the animation states a tank could be in."""
    Normal = auto()
    Falling = auto()


class TankObject(Object):
    """All of the data and functionality representing a tank, whether is be a player or an AI."""
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
        self.collision_radius: float = 35

        # AI private variables
        self.is_player_character: bool = False
        self.accuracy_multiplier: float = 0.001
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

    def take_damage(self, damage: int):
        """
        Decrease the health points by damage. Returns the current health point after damage is taken. Kills the tank
        if damage is less than 0.
        :param damage: is the number of hp to reduce.
        :return: the number of health_points after taking damage.
        """
        # print('Tank took damage!')
        # The volume with which we will play the "OW" sound. It'll be loud if it does more relative damage.
        # volume = damage / self.health_points
        self.health_points -= damage
        if self.health_points <= 0:
            self.current_state = TankState.Dead
            self.kill()
        self.play_sound(self.damage_sound)
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
        self.rotation_speed = 0

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
                'tread_x': 1,
                'tread_y': 1,
                'angle': self.angle,
                'longitude': self.longitude,
                'health': self.health_points,
                'selected_bullet': self.selected_bullet,
                'bullet_counts': self.bullet_counts,
                'bullet_sprites': [str(bullet_type) for bullet_type in self.bullet_types],
                'sound': str(self.sound_type_to_play)}

    def think(self):
        """
        "Smart" AI
        This "Smart" AI is implemented as a glorified state machine.
        States: Manual, Move, MoveLeft, MoveRight, Aim, AimLeft, AimRight, Power, PowerUp, PowerDown, Fire, Wait, Think
        :return:
        """
        # print(f' Tank { self.id} is thinking', self.current_state)
        # Switch over the current state
        if self.current_state == TankState.Wait:
            self._tank_state_wait()

        # Think == Make a plan for this turn
        elif self.current_state == TankState.Think:
            self._tank_state_think()

        # Move the tank left or right
        elif self.current_state == TankState.Move:
            self._tank_state_move()

        # Aim the turret
        elif self.current_state == TankState.Aim:
            self._tank_state_aim()

        # Get to the correct power
        elif self.current_state == TankState.Power:
            self._tank_state_power()

        # Fire!
        elif self.current_state == TankState.Fire:
            self._tank_state_fire()

        # FireWait is when we're waiting on the ObjectManager to fire the gun for us
        elif self.current_state == TankState.FireWait:
            self._tank_state_firewait()

        # Post fire states
        elif self.current_state == TankState.PostFire:
            self._tank_state_postfire()

        # Dead
        elif self.current_state == TankState.Dead:
            self._tank_state_dead()

        # If the current state is manual, do nothing
        elif self.current_state == TankState.Manual:
            self._tank_state_manual()

        # If unknown case, switch to waiting
        else:
            self.current_state = TankState.Wait

    def _tank_state_manual(self):
        pass

    def _tank_state_dead(self):
        if self.dead and turns_enabled:
            # TODO: Implement turns
            # m_pPlayer = m_pTurnManager->NextTurn();
            pass

    def _tank_state_postfire(self):
        if not turns_enabled:
            if self.is_player_character:
                self.current_state = TankState.Manual
            else:
                self.current_state = TankState.Wait
        else:
            # TODO: Implement turns
            pass

    def _tank_state_firewait(self):
        pass

    def _tank_state_fire(self):
        if datetime.datetime.now().timestamp() > self.gun_timer + 3:
            # Choose a random bullet that we have access to.
            self.selected_bullet = randint(0, self.bullet_type_count)

            self.current_state = TankState.FireWait
            # self.current_state = TankState.PostFire

    def _tank_state_power(self):
        if self.desired_power - self.power > 50:
            self.power_speed = 50
        elif self.desired_power - self.power < -50:
            self.power_speed = -50
        else:
            self.current_state = TankState.Fire
            self.power_speed = 0

    def _tank_state_aim(self):
        self.desired_angle = self.desired_angle % 360
        # How far apart are the angles in positive degrees?
        diff_angle: float = (self.angle - self.desired_angle) % 360
        # The difference being greater than 1 gives us some buffer. It's unlikely that we'll ever get angle and
        # desired_angle to be exactly correct with how the steptimer works.
        if 180 < diff_angle < 1:
            self.rotation_speed = 1
        elif 180 > diff_angle > 1:
            self.rotation_speed = -1
        else:
            self.current_state = TankState.Power
            self.rotation_speed = 0

    def _tank_state_move(self):
        # How far apart are the angles in positive degrees?
        diff_angle: float = (self.longitude - self.desired_longitude) % 360
        # If the difference is less than 180, it's faster to go left.
        # Buffer of 2 degrees longitude to prevent spazzing.
        if 180 > diff_angle > 2:
            self.strafe_right = True
        # If the difference is greater than 180, it's faster to go right.
        # Buffer of 5 degrees longitude to prevent spazzing.
        elif 180 < diff_angle < 2:
            self.strafe_left = True
        else:
            self.current_state = TankState.Aim

    def _tank_state_think(self):
        # We have to wait for the Object Manager to aim for us.
        # self.adjust_aim()
        # self.current_state = TankState.Move
        pass

    def _tank_state_wait(self):
        # Make sure not dead
        if self.dead:
            self.current_state = TankState.Dead
        # Make sure not player
        if self.is_player_character:
            self.current_state = TankState.Manual
        # Check if it's my turn. If so, switch to think. If not, do nothing.
        if not turns_enabled and not self.is_player_character:
            self.current_state = TankState.Think
