from datetime import datetime
from itertools import product
from math import pi, cos, sin, atan2, sqrt
from random import random, randint, choice
from typing import List, Dict, Optional, Callable

from socketio import AsyncServer

from . import Common
from .BulletObject import BulletObject
from .Config import gravity_constant, turns_enabled
from .PlanetObject import PlanetObject
from .PlayerInfo import PlayerInfo
from .SpriteType import SpriteType
from .TankObject import TankObject, TankState
from .WormholeObject import WormholeObject
from .vector import Vector, Sphere, UnitVector


def only_if_current_player(func: Callable) -> Callable:
    """
    """

    def wrapper(*args, **kwargs):
        self = args[0]  # Only call this on instance methods
        sid = args[1]
        if sid == self.current_player_sid or not self.turns_enabled:
            result = func(*args, **kwargs)
            return result

    return wrapper


class ObjectManager:
    def __init__(self, sio: Optional[AsyncServer] = None, file_path: str = ''):
        self.explosions = []
        self.users = []
        self.sockets = {}
        self.planets: Dict[str, PlanetObject] = {}
        self.tanks: Dict[str, TankObject] = {}
        self.bullets: List[BulletObject] = []
        self.wormholes: List[WormholeObject] = []

        self.sio: Optional[AsyncServer] = sio

        self.gravity_constant: float = gravity_constant  # Gravity Constant in Newton's Law of Universal Gravitation
        self.softening_parameter: float = 0
        self.dt: float = .001  # Time step for physics calculations

        self.level_name: str = ''
        self.world_size = Vector(0, 0)
        self.game_started: bool = False
        self.file_path: str = file_path or './levels/Stage 1/I Was Here First!.txt'
        if self.file_path:
            self.load_level_file(self.file_path)

        # Turn Manager Functionality
        self.turns_enabled = turns_enabled
        self.current_player_sid: Optional[str] = None  # The current turn (# tank that input is controlling)
        self.current_tank: Optional[TankObject] = None  # The current tank whose turn it is
        self.total_turns: int = 0  # Total turns taken
        self.num_human_players: int = 0  # Number of human players
        self.current_player_fired_gun: bool = False  # Keep track if the current player has fired their gun

    def create_planet(self, position: Vector, mass: float = 0, radius: int = 500) -> PlanetObject:
        """
        Create a new Planet
        :param position: Vector position of the new planet
        :param mass: float mass of the planet
        :param radius: int radius of planet
        :return: the planet object
        """
        planet = PlanetObject(position, radius)
        if mass:
            planet.mass = mass
        self.planets[planet.id] = planet
        return planet

    def create_tank(self, longitude: float, home_planet: PlanetObject, sid: str, color: str = '',
                    is_player: bool = False) -> TankObject:
        """
        Create a new Tank
        :param is_player: True if the tank represents a player. Otherwise false.
        :param longitude: float longitude of the tank (angle relative to the planet)
        :param home_planet: PlanetObject of the home planet
        :param color: string representing the color hue of the tank
        :param sid: string representing the
        :return:
        """
        tank = TankObject(longitude=longitude, planet=home_planet, color=color)
        tank.is_player_character = is_player
        if sid not in [user.id for user in self.users]:
            self.users.append(PlayerInfo(sid, 0, 0, 0, 'ai', 0, Vector(0, 0), sid))

        self.tanks[sid] = tank
        return tank

    def create_bullet(self, bullet_sprite: SpriteType, position: Vector, trail_color: str = '') -> BulletObject:
        """

        :param bullet_sprite:
        :param position:
        :param trail_color:
        :return:
        """
        bullet = BulletObject(position, bullet_sprite)
        bullet.hue = trail_color
        self.bullets.append(bullet)
        return bullet

    def create_phantom_bullet(self, bullet, position, velocity, owner) -> float:
        """

        :param bullet:
        :param position:
        :param velocity:
        :param owner:
        :return:
        """
        phantom_bullet = BulletObject(position, bullet)
        phantom_bullet.velocity = velocity
        phantom_bullet.owner = owner
        datetime.now().timestamp()
        dt = self.dt
        # Force it to the next place if it's not dead without waiting for the physics engine to catch up
        for _ in range(1000):
            if not phantom_bullet.dead:
                phantom_bullet.acceleration = self.calculate_gravity(phantom_bullet.position)
                phantom_bullet.velocity += phantom_bullet.acceleration * dt
                phantom_bullet.position += phantom_bullet.velocity * dt
                # phantom_bullet.move()
                # Check for planet collisions
                for _, planet in self.planets.items():
                    if planet.intersects(phantom_bullet.collision_sphere):
                        phantom_bullet.dead = True
                    # TODO: Deal with world edge
                    # TODO: Implement Wormholes
        final_pos = phantom_bullet.position
        # TODO: De-incentivize suicide shots by figuring out how to maximize how far away it is from the player
        self_distance = abs(owner.position - final_pos)
        if self_distance > 50:
            self_distance = 1
        return self.get_nearest_tank_location(final_pos, owner)

    def move_bullet(self, bullet):
        old_position: Vector = bullet.position
        if self.at_world_edge(old_position):
            bullet.kill()

        if bullet.splitter:
            if datetime.now().timestamp() - bullet.time_created >= bullet.splitter_time != 0:
                rads: float = 20.0 * pi / 180  # Convert degrees to radians
                for i in range(bullet.splitter_counter):
                    new_bullet = self.create_bullet(bullet_sprite=bullet.sprite_type,
                                                    position=old_position,
                                                    trail_color=bullet.hue)
                    new_bullet.owner = bullet.owner
                    new_bullet.roll = bullet.roll
                    new_bullet.time_to_live = 15
                    new_bullet.splitter = False

                    # Move the bullets into trajectories that are rads apart.
                    new_bullet.velocity = bullet.velocity
                    if i == 0:
                        new_bullet.velocity = bullet.velocity.rotate(rads)
                    elif i == 1:
                        new_bullet.velocity = bullet.velocity.rotate(-rads)
                    new_bullet.velocity *= 1.25
                bullet.kill()

        bullet.acceleration = self.calculate_gravity(old_position)
        if bullet.accelerator:
            bullet.acceleration += bullet.velocity
        # print('Bullet position:', bullet.position, abs(bullet.position))
        # print('Bullet acceleration:', bullet.acceleration, abs(bullet.acceleration))
        bullet.move()

    def move_tank(self, sid: str, tank: TankObject, currently_my_turn=True):
        # old_position: Vector = tank.position
        if currently_my_turn:
            tank.think()
            if tank.current_state == TankState.FireWait:
                self.fire_gun_sid(sid)
                tank.current_state = TankState.PostFire
            elif tank.current_state == TankState.Think:
                self.adjust_aim(tank)
                tank.current_state = TankState.Move
            elif tank.current_state == TankState.PostFire:
                if tank.is_player_character:
                    tank.current_state = TankState.Manual
                else:
                    tank.current_state = TankState.Wait
        tank.move(currently_my_turn=currently_my_turn)

    async def move(self, server: AsyncServer):
        """
        Move all of the objects and perform collision detection and response
        :return:
        """
        if not self.game_started:
            return
        for bullet in self.bullets:
            self.move_bullet(bullet)
        if self.turns_enabled:
            if not len(self.bullets):
                self.move_tank(self.current_player_sid, self.current_tank)
            if self.current_player_fired_gun and not len(self.bullets):
                self.current_player_fired_gun = False
                await self.next_turn()
        for sid, tank in self.tanks.items():
            self.move_tank(sid, tank, currently_my_turn=False)

        self.collision_phase()
        await self.cull_dead_objects(server)

    def calculate_gravity(self, position) -> Vector:
        acceleration: Vector = Vector(0, 0)
        for _, planet in self.planets.items():
            difference: Vector = planet.position - position
            mag = abs(difference)
            unit = difference / mag

            acceleration += gravity_constant * planet.mass / mag ** 2 * unit
        return acceleration

    def at_world_edge(self, old_position) -> bool:
        return (old_position.x < 0 or old_position.x > self.world_size.x or
                old_position.y < 0 or old_position.y > self.world_size.y)

    async def send_objects_initial(self, sio: AsyncServer, *args, **kwargs):
        for planet in self.planets.values():
            await planet.emit_initial(sio, *args, **kwargs)
        await sio.emit('turns_enabled', {'turns_enabled': self.turns_enabled})
        # for user in self.users:
        #     await user.emit_initial(self.tanks, sio, *args, **kwargs)

    async def send_updates(self, sio: AsyncServer, *args, **kwargs):
        for planet in self.planets.values():
            await planet.emit_changes(sio, *args, **kwargs)

        # It creates rendering issues (graphical stuttering) when we send the tanks one at a time.
        # Avoid this by sending all in one msg.
        await sio.emit('update-tanks',
                       [users.get_changes(self.tanks) for users in self.users],
                       *args, **kwargs)
        # for user in self.users:
        #     await user.emit_changes(self.tanks, sio, *args, **kwargs)

        # It creates rendering issues (graphical stuttering) when we send the bullets one at a time.
        # Avoid this by sending all in one msg.
        await sio.emit('update-bullets',
                       [bullet.get_json() for bullet in self.bullets],
                       *args, **kwargs)
        # for bullet in self.bullets:
        #   await bullet.emit_changes(sio)

        # Send explosions
        await sio.emit('update-explosions', self.explosions)
        self.explosions = []

        # for u in self.users:
        #     # center the view if x/y is undefined, this will happen for spectators
        #     u.x = u.x or ConfigData.gameWidth / 2
        #     u.y = u.y or ConfigData.gameHeight / 2
        #
        #     def user_mapping_function(f):
        #         if f.id != u.id:
        #             return {'id': f.id,
        #                     'x': f.x,
        #                     'y': f.y,
        #                     'hue': f.hue,
        #                     'name': f.name
        #                     }
        #         else:
        #             return {'x': f.x,
        #                     'y': f.y,
        #                     'hue': f.hue,
        #                     'name': f.name
        #                     }
        #
        #     user_transmit = [user_mapping_function(x) for x in self.users]
        #     sid = self.sockets[u.id]
        #     await sio.emit('serverTellPlayerMove', [user_transmit, [], [], []], room=sid)

    async def strafe_right(self, sid):
        try:
            self.tanks[sid].strafe_right = True
            await self.calculate_current_player_trajectory(self.sio)
        except KeyError:  # Dead player trying to move. Avoid crash
            pass

    async def strafe_left(self, sid):
        try:
            self.tanks[sid].strafe_left = True
            await self.calculate_current_player_trajectory(self.sio)
        except KeyError:  # Dead player trying to move. Avoid crash
            pass

    def remove_player(self, sid):
        try:
            del self.tanks[sid]
            self.sockets.pop(sid)
        except KeyError:
            pass
        try:
            for i in range(len(self.users)):
                if self.users[i].id == sid:
                    self.users.pop(i)
        except IndexError:
            pass

    async def angle_left(self, sid):
        try:
            self.tanks[sid].rotation_speed = -1
            await self.calculate_current_player_trajectory(self.sio)
        except KeyError:
            pass

    async def angle_right(self, sid):
        try:
            self.tanks[sid].rotation_speed = 1
            await self.calculate_current_player_trajectory(self.sio)
        except KeyError:
            pass

    def fire_gun(self, bullet: SpriteType, owner: TankObject) -> None:
        """
        Create a bullet object and a flash particle effect.
        It is assumed that the object is round and that the bullet
        appears at the edge of the object in the direction
        that it is facing and continues moving in that direction.
        :param owner:
        :param bullet: sprite type of the bullet
        :return:
        """

        if owner.dead:  # We don't want to shoot if we're supposed to be dead.
            return
        # TODO: Play audio

        view: Vector = -owner.view_vector
        pos: Vector = owner.position

        # Set camera and control lock

        if self.turns_enabled:
            Common.control_lock = True
            Common.camera_mode = Common.CameraMode.BULLET_LOCKED

        bullet = self.create_bullet(bullet, pos, owner.hue)
        bullet.owner = owner

        deflection = Vector(0, 0)

        bullet.velocity = owner.power * (view + deflection)  # Power is the starting velocity
        bullet.roll = owner.roll
        bullet.hue = owner.hue

        if owner.selected_bullet not in (0, 1):
            owner.bullet_counts[owner.selected_bullet] -= 1
        while not owner.bullet_counts[owner.selected_bullet]:
            owner.next_bullet_type()

        owner.gun_timer = datetime.now().timestamp()

        # TODO: Gunfire particle effect on client side

    def fire_phantom_gun(self, bullet: SpriteType, orientation: Vector, power: float, owner: TankObject,
                         position: Vector = None) -> float:
        """

        :param bullet:
        :param orientation:
        :param power:
        :param owner:
        :param position:
        :return:
        """
        if position is None:  # In the default case, use the current position
            position = owner.position
        position = position + .5 * owner.collision_radius * orientation
        power = owner.power

        # to get better results, we should average this over a couple shots with adjusted angles/power.
        # The physics simulations will mess us up quite frequently.
        num_simulations: int = 3
        running_distance_sum: float = 0
        for i in range(num_simulations):
            if i:
                power /= 1.01
                velocity = owner.velocity + power * orientation  # Power is the starting velocity
                running_distance_sum += self.create_phantom_bullet(bullet, position, velocity, owner)
        return running_distance_sum / num_simulations

    def fire_gun_sid(self, sid):
        try:
            if sid == self.current_player_sid or not self.turns_enabled:
                tank = self.tanks[sid]
                tank.selected_bullet = tank.selected_bullet % len(tank.bullet_counts)
                if tank.bullet_counts[tank.selected_bullet] > 0:
                    self.fire_gun(tank.bullet_types[tank.selected_bullet], tank)
                    if sid == self.current_player_sid:
                        self.current_player_fired_gun = True
        except KeyError:  # If no tank shows up with that sid, then they are dead
            pass

    def collision_phase(self):
        # for bullet, wormhole in product(self.bullets, self.wormholes):
        #     if wormhole.next_wormhole is not None and wormhole.collision_sphere.intersects_circle_fast(
        #             bullet.collision_sphere):
        #         bullet.position = wormhole.next_wormhole.position
        #         bullet.position += 1.2 * (
        #                     wormhole.collision_sphere.radius + bullet.collision_sphere.radius) * bullet.velocity

        for bullet, tank in product(self.bullets, list(self.tanks.values())):
            intersects = bullet.collision_sphere.intersects_circle_fast(tank.collision_sphere)
            # If the bullet intersects a tank
            # Additionally, we don't want the bullets to "misfire" i.e. explode before leaving the tank that
            # shot them.
            if intersects and tank != bullet.owner:
                self._explode_bullet(bullet, tank=tank)
                tank.take_damage(bullet.damage)

        for bullet, planet in product(self.bullets, list(self.planets.values())):
            if planet.intersects(bullet.collision_sphere):
                self._explode_bullet(bullet, planet)

    def _explode_bullet(self, bullet: BulletObject, planet: PlanetObject = None, tank: TankObject = None):
        self.explosions.append({'x': bullet.position.x,
                                'y': bullet.position.y,
                                'sprite': str(bullet.explosion_sprite),
                                'radius': bullet.explosion_radius,
                                'sound': str(bullet.explosion_sound)})
        self.damage_players_in_sphere(Sphere(bullet.position, bullet.explosion_radius), bullet.damage)
        if bullet.destroys_terrain:
            damage_sphere = Sphere(bullet.position, bullet.explosion_radius)
            if tank and not planet:
                planet = tank.home_planet
            if planet:
                planet.destroy_terrain(damage_sphere)
        if bullet.generates_terrain:
            damage_sphere = Sphere(bullet.position, bullet.explosion_radius)
            if tank and not planet:
                planet = tank.home_planet
            if planet:
                planet.generate_terrain(damage_sphere)
        if bullet.bounce_limit > 0 and bullet.bounces < bullet.bounce_limit:
            self.bounce_bullet(planet, bullet)
        if bullet.teleporter:
            # Teleport the owner to where this collision is
            bullet.owner.teleport(bullet.position, planet)
        if bullet.creates_wormholes:
            self._spawn_wormholes(bullet, planet)
        bullet.kill()

    def _spawn_wormholes(self, bullet, planet):
        # Create 2 wormholes
        delta = bullet.position - planet.position
        angle = atan2(delta.x, -delta.y) * 180 / pi + 90

        dir1vec: Vector = UnitVector(angle * pi / 180)
        dir2vec: Vector = Vector(x=cos(angle + 180 * pi / 180),
                                 y=sin(-angle * pi / 180))
        # Generate wormholes 350 units above sea level
        worm1pos: Vector = planet.position + dir1vec * (planet.sealevel_radius + 350)
        worm2pos: Vector = planet.position + dir2vec * (planet.sealevel_radius + 350)
        w1 = self.create_wormhole(worm1pos, len(self.tanks) * 2)
        w2 = self.create_wormhole(worm2pos, len(self.tanks) * 2, w1)
        w1.next_wormhole = w2

    def bounce_bullet(self, planet: PlanetObject, bullet: BulletObject):
        # Bounce along the surface of the planet
        planet_pos = planet.position
        bullet_pos = bullet.position
        bullet_vel = bullet.velocity

        normal: Vector = planet_pos - bullet_pos  # Normal vector to the surface
        normal = normal / abs(normal)  # Unit normal
        # Create a new bullet that bounces off. We wil recursively make more bullets until out of bounces
        # Create the next bullet above the planet surface, so that we don't collide with planet immediately
        new_bullet = self.create_bullet(bullet.sprite_type,
                                        Vector(x=bullet_pos.x + (-normal.x * 10),
                                               y=bullet_pos.y + (-normal.y * 10)),
                                        trail_color=bullet.hue)
        new_bullet.owner = bullet.owner
        new_bullet.velocity = -(2 * (normal * bullet_vel) * normal - bullet_vel)  # Follow the law of reflection
        new_bullet.bounces = bullet.bounces + 1

    async def cull_dead_objects(self, server: AsyncServer):
        dead_bullets = [bullet for bullet in self.bullets if bullet.dead]
        for bullet in dead_bullets:
            self.bullets.remove(bullet)

        dead_tanks_sids = [sid for sid, tank in self.tanks.items() if tank.dead]
        for sid in dead_tanks_sids:
            self.tanks.pop(sid)
            await server.emit('RIP', room=sid)

    async def power_up(self, sid):
        try:
            player = self.tanks[sid]
            player.power += 2
            player.power = min(player.power, player.basePower + player.currentFuel)
            await self.calculate_current_player_trajectory(self.sio)
        except KeyError:
            # Player is dead
            pass

    async def power_down(self, sid):
        try:
            player = self.tanks[sid]
            player.power -= 2
            player.power = max(player.power, 1)
            await self.calculate_current_player_trajectory(self.sio)
        except KeyError:
            # Player is dead
            pass

    def damage_players_in_sphere(self, sphere: Sphere, damage: int) -> None:
        """
        Iterate over all the players and damage them if they are inside the explosion sphere
        :param sphere: BoundingSphere representing the explosion
        :param damage: how much to damage players.
        :return:
        """
        for _, tank in self.tanks.items():
            intersect = sphere.intersects_circle_fast(tank.collision_sphere)
            if intersect:
                tank.take_damage(damage)

    def load_level_file(self, path: str):
        """
        Load a level file at the given path
        :param path: url to the correct file
        :return:
        """
        i = 0
        with open(path, 'r') as file:
            lines = file.readlines()
            for line in lines:
                pieces = line.split()
                if pieces[0] == 'NAME':
                    self.level_name = ' '.join(pieces[1:])
                elif pieces[0] == 'WORLD':
                    w = int(pieces[1])  # width
                    h = int(pieces[2])  # height
                    self.world_size = Vector(w, h)
                elif pieces[0] == 'PLANET':
                    self.create_planet(Vector(int(pieces[1]), int(pieces[2])),
                                       mass=int(pieces[3]),
                                       radius=int(pieces[4]))
                elif pieces[0] == 'TANK':
                    # Todo get planet number (which is pieces[2], since self.planets is a dict
                    if bool(int(pieces[4])):
                        self.create_tank(float(pieces[1]), choice(list(self.planets.values())), sid=f'ai-{i}',
                                         color=pieces[3],
                                         is_player=False  # is_player=bool(int(pieces[4]))
                                         )
                    i += 1

    def next_bullet(self, sid):
        self.tanks[sid].selected_bullet = (self.tanks[sid].selected_bullet + 1) % len(self.tanks[sid].bullet_counts)

    def random_aim_once(self, tank: TankObject, longitude):
        # Randomize the aim parameters
        test_angle = randint(-15, 195) % 360
        test_longitude = longitude
        test_power = float(randint(50, 1000))
        test_roll = pi + (test_angle + test_longitude) * pi / 180
        view = Vector(-sin(test_roll), cos(test_roll))  # Orientation of the phantom bullet.
        new_distance = self.fire_phantom_gun(SpriteType.WATER_SPRITE, view, test_power, tank, tank.position)
        return test_angle, test_power, test_roll, new_distance

    def adjust_aim(self, tank: TankObject, monte_carlo: bool = True):
        """

        :param tank:
        :param monte_carlo:
        :return:
        """
        test_angle: float = tank.desired_angle
        test_longitude: float = tank.desired_longitude + randint(-10, 10)
        test_power: float = tank.desired_power
        # Set the roll so that it compensates for the inclination on the planet
        test_roll: float = pi + (test_angle + test_longitude) * pi / 180
        view: Vector = Vector(-sin(test_roll), cos(test_roll))  # Orientation of the phantom bullet.
        previous_distance = self.fire_phantom_gun(SpriteType.WATER_SPRITE, view, test_power, tank,
                                                  tank.position)  # Initial guess, so we have something to compare to.
        if monte_carlo:
            trials = [self.random_aim_once(tank, test_longitude) for _ in range(int(1000 * tank.accuracy_multiplier))]
            for test_angle, test_power, test_roll, new_distance in trials:
                if new_distance < previous_distance:
                    previous_distance = new_distance
                    deflection = 2.5 * (2 * random() - 1)
                    tank.desired_angle = test_angle + deflection
                    tank.desired_longitude = test_longitude
                    tank.desired_power = test_power
        else:
            # Implement either gradient descent and/or particle swarm optimization
            """"""
            print()

    def get_nearest_tank_location(self, position: Vector, origin: TankObject):
        current_closest_length = -1
        distance: float = 0
        for _, tank in self.tanks.items():
            if tank != origin and not tank.dead:
                distance = abs(position - tank.position)
                # distance /= 1 - exp(-abs(origin.position - tank.position)**2/250)

        if current_closest_length == -1 or distance < current_closest_length:
            current_closest_length = distance
        # TODO: Wormholes and suicide shots
        return current_closest_length

    def create_wormhole(self, wormhole_position: Vector, time_to_live: int, next_wormhole: WormholeObject = None):
        wormhole = WormholeObject(wormhole_position, time_to_live, next_wormhole)
        self.wormholes.append(wormhole)
        return wormhole

    def reset(self, file_path=''):
        file_path = file_path or self.file_path
        self.__init__(self.sio, file_path)

    async def calculate_trajectory(self, t: SpriteType, position: Vector, velocity: Vector, owner: TankObject):
        # print('Calculating trajectory:', owner, position, velocity)
        phantom_bullet = BulletObject(position, sprite_type=t)
        phantom_bullet.owner = owner
        phantom_bullet.is_phantom = True
        phantom_bullet.velocity = velocity
        positions = []
        # Step it 200 times at once
        for _ in range(200):
            phantom_bullet.acceleration = self.calculate_gravity(phantom_bullet.position)
            phantom_bullet.move()
            # Check for collisions with planets
            for planet in self.planets.values():
                if planet.intersects(phantom_bullet.collision_sphere):
                    phantom_bullet.dead = True
                    break
            if self.at_world_edge(phantom_bullet.position):
                phantom_bullet.dead = True
                break
            if phantom_bullet.dead:
                break

            positions.append((int(phantom_bullet.position.x), int(phantom_bullet.position.y)))

        del phantom_bullet
        return positions

    async def calculate_current_player_trajectory(self, sio, *args, **kwargs):
        tank = self.current_tank
        positions = await self.calculate_trajectory(t=tank.bullet_types[tank.selected_bullet],
                                                    position=tank.position,
                                                    velocity=tank.power * -tank.view_vector,
                                                    owner=tank)
        await sio.emit('trajectory', {'hue': tank.hue, 'positions': positions},
                       room=self.current_player_sid,
                       *args, **kwargs)

    async def calculate_all_trajectories(self, sio: AsyncServer, *args, **kwargs):
        for user in self.users:
            sid = user.id
            try:
                tank = self.tanks[sid]
                positions = await self.calculate_trajectory(t=tank.bullet_types[tank.selected_bullet],
                                                            position=tank.position,
                                                            velocity=tank.power * -tank.view_vector,
                                                            owner=tank)
                await sio.emit('trajectory', {'hue': tank.hue, 'positions': positions}, room=sid, *args, **kwargs)
            except KeyError:
                pass

    @property
    def is_game_over(self) -> bool:
        """
        Calculates if the game is over by checking if started and the number of living tanks.
        If there are less than 2 (i.e. 1 or 0 live tanks), then the game is over.
        :return: None
        """
        return self.game_started and self.num_tanks_alive < 2

    def disconnect_player(self, sid: str) -> None:
        """
        Sets the tank with id equal to sid to be an AI tank. This is used when a player disconnected before the
        round is over.
        :param sid: Socket-id of the player that disconnected
        :raise TankDoesNotError when no tank exists with the given sid
        """
        try:
            self.tanks[sid].is_player_character = False
            self.tanks[sid].current_state = TankState.Wait
        except KeyError:
            pass

    def reconnect_player(self, sid: str):
        """
        Sets the tank with id equal to sid to be an player tank. This is used when a player disconnected before the
        round is over, but later reconnected
        :param sid: Socket-id of the player that reconnected
        :raise TankDoesNotError when no tank exists with the given sid
        """
        self.tanks[sid].is_player_character = True
        self.tanks[sid].current_state = TankState.Manual

    @property
    def num_players(self) -> int:
        return len(self.tanks)

    @property
    def num_tanks_alive(self) -> int:
        return len([tank for tank in self.tanks.values() if not tank.dead])

    async def next_turn(self) -> TankObject:
        """
        Gives turn to the next tank in the list, wrapping around when the end is reached.
        :return:
        """
        found_it: bool = False
        while not self.is_game_over:
            for sid, tank in self.tanks.items():
                if sid == self.current_player_sid:
                    found_it = True
                elif found_it and not tank.dead:
                    self.current_player_sid, self.current_tank = sid, tank
                    await self.sio.emit('next-turn', {'current_player': self.current_player_sid})
                    return self.current_tank

    async def set_turn(self, tank_sid: str) -> TankObject:
        """
        Sets the turn to the tank, instead of incrementing to the next one.
        :param tank_sid:
        :return:
        """
        self.current_player_sid, self.current_tank = tank_sid, self.tanks[tank_sid]
        await self.sio.emit('next-turn', {'current_player': self.current_player_sid})
        return self.current_tank

    async def start_game(self) -> None:
        self.game_started = True
        self.current_player_sid, self.current_tank = list(self.tanks.items())[0]  # Pick the first player
        await self.sio.emit('next-turn', {'current_player': self.current_player_sid})

    async def update_target(self, player_sid, target):
        if self.current_player_sid == player_sid:
            tank = self.tanks[player_sid]
            # Set Angle
            tank.angle = atan2(target.y, target.x) * (180/pi) - tank.longitude + 270
            # Set Power
            tank.power = min(1.5 * sqrt(target.x**2 + target.y**2), tank.basePower + tank.currentFuel)
            await self.calculate_current_player_trajectory(self.sio)

