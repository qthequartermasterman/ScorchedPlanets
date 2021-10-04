from datetime import datetime
from math import pi, cos, sin, exp
from random import random, randint, choice
from typing import List, Dict
from itertools import product

from socketio import AsyncServer

from . import Common
from .BulletObject import BulletObject
from .Config import ConfigData, gravity_constant, turns_enabled
from .PlanetObject import PlanetObject
from .PlayerInfo import PlayerInfo
from .SpriteType import SpriteType
from .TankObject import TankObject, TankState
from .vector import Vector, Sphere


class ObjectManager:
    def __init__(self):
        self.explosions = []
        self.users = []
        self.sockets = {}
        self.planets: Dict[str, PlanetObject] = {}
        self.tanks: Dict[str, TankObject] = {}
        self.bullets: List[BulletObject] = []

        self.gravity_constant: float = gravity_constant  # Gravity Constant in Newton's Law of Universal Gravitation
        self.softening_parameter: float = 0

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
        start_time = datetime.now().timestamp()
        dt = .1
        # Force it to the next place if it's not dead without waiting for the physics engine to catch up
        while not phantom_bullet.dead:
            phantom_bullet.acceleration = self.calculate_gravity(phantom_bullet.position)
            phantom_bullet.velocity += phantom_bullet.acceleration * dt
            phantom_bullet.move()
            # Check for planet collisions
            for _, planet in self.planets.items():
                if planet.intersects(phantom_bullet.collision_sphere):
                    phantom_bullet.dead = True
                # TODO: Deal with world edge
                # TODO: Implement Wormholes
        final_pos = phantom_bullet.position
        # TODO: Deincentivize suicide shots by figuring out how to maximuze how far away it is from the player
        self_distance = abs(owner.position-final_pos)
        if self_distance > 50:
            self_distance = 1
        return self.get_nearest_tank_location(final_pos, owner)

    async def move(self, server: AsyncServer):
        """
        Move all of the objects and perform collision detection and response
        :return:
        """
        dt: float = 0.1
        for bullet in self.bullets:
            old_position: Vector = bullet.position
            if self.at_world_edge(old_position):
                bullet.kill()
            bullet.acceleration = self.calculate_gravity(old_position)
            # print('Bullet position:', bullet.position, abs(bullet.position))
            # print('Bullet acceleration:', bullet.acceleration, abs(bullet.acceleration))
            bullet.move()

        for sid, tank in self.tanks.items():
            old_position: Vector = tank.position
            tank.think()
            if tank.current_state == TankState.FireWait:
                self.fire_gun_sid(sid)
                tank.current_state = TankState.PostFire
            elif tank.current_state == TankState.Think:
                self.adjust_aim(tank)
                tank.current_state = TankState.Move
            tank.move()

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

    def at_world_edge(self, oldpos) -> bool:
        return False

    async def send_objects_initial(self, sio: AsyncServer, *args, **kwargs):
        for planet in self.planets.values():
            await planet.emit_initial(sio, *args, **kwargs)
        # for user in self.users:
        #     await user.emit_initial(self.tanks, sio, *args, **kwargs)

    async def send_updates(self, sio: AsyncServer, *args, **kwargs):
        # await sio.emit('serverTellPlayerMove', [visibleCells, visibleFood, visibleMass, visibleVirus], room=sid)
        for planet in self.planets.values():
            await planet.emit_changes(sio, *args, **kwargs)

        # It creates rendering issues (graphical stuttering) when we send the bullets one at a time.
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

    def strafe_right(self, sid):
        try:
            self.tanks[sid].strafe_right = True
        except KeyError:  # Dead player trying to move. Avoid crash
            pass

    def strafe_left(self, sid):
        try:
            self.tanks[sid].strafe_left = True
        except KeyError:  # Dead player trying to move. Avoid crash
            pass

    def remove_player(self, sid):
        try:
            del self.tanks[sid]
        except KeyError:
            pass
        try:
            for i in range(len(self.users)):
                if self.users[i].id == sid:
                    self.users.pop(i)
        except IndexError:
            pass

    def angle_left(self, sid):
        self.tanks[sid].rotation_speed = -1

    def angle_right(self, sid):
        self.tanks[sid].rotation_speed = 1

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

        if turns_enabled:
            Common.control_lock = True
            Common.camera_mode = Common.CameraMode.BULLET_LOCKED

        bullet = self.create_bullet(bullet, pos, owner.hue)
        bullet.owner = owner

        norm: Vector = Vector(view.y, -view.x)  # normal to direction
        m: float = 2 * random() - 1
        deflection = Vector(0, 0)

        bullet.velocity = owner.power * (view + deflection)  # Power is the starting velocity
        bullet.roll = owner.roll

        if owner.selected_bullet not in (0, 1):
            owner.bullet_counts[owner.selected_bullet] -= 1
        while not owner.bullet_counts[owner.selected_bullet]:
            owner.next_bullet_type()

        owner.gun_timer = datetime.now().timestamp()

        # TODO: Gunfire particle effect on client side

    def fire_phantom_gun(self, bullet: SpriteType, orientation: Vector, power: float, owner: TankObject,
                         position: Vector = Vector(0, 0)) -> float:
        """

        :param bullet:
        :param orientation:
        :param power:
        :param owner:
        :param position:
        :return:
        """
        if position == Vector(0, 0):  # In the default case, use the current position
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
            tank = self.tanks[sid]
            tank.selected_bullet = tank.selected_bullet % len(tank.bullet_counts)
            if tank.bullet_counts[tank.selected_bullet] > 0:
                self.fire_gun(tank.bullet_types[tank.selected_bullet], tank)
        except KeyError:  # If no tank shows up with that sid, then they are dead
            pass

    def collision_phase(self):
        for bullet, tank in product(self.bullets, list(self.tanks.values())):
            intersects, _, _ = bullet.collision_sphere.intersects_circle(tank.collision_sphere)
            # If the bullet intersects a tank
            # Additionally, we don't want the bullets to "misfire" i.e. explode before leaving the tank that
            # shot them.
            if intersects and tank != bullet.owner:
                self._explode_bullet(bullet)
                tank.take_damage(bullet.damage)

        for bullet, planet in product(self.bullets, list(self.planets.values())):
            if planet.intersects(bullet.collision_sphere):
                self._explode_bullet(bullet, planet)

    # TODO Rename this here and in `collision_phase`
    def _explode_bullet(self, bullet, planet: PlanetObject = None, tank: TankObject = None):
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
        bullet.kill()

    async def cull_dead_objects(self, server: AsyncServer):
        await self.send_updates(server)
        dead_bullets = [bullet for bullet in self.bullets if bullet.dead]
        for bullet in dead_bullets:
            self.bullets.remove(bullet)

        dead_tanks_sids = [sid for sid, tank in self.tanks.items() if tank.dead]
        for sid in dead_tanks_sids:
            self.tanks.pop(sid)
            await server.emit('RIP', room=sid)

    def power_up(self, sid):
        try:
            player = self.tanks[sid]
            player.power += 2
            player.power = min(player.power, player.basePower + player.currentFuel)
        except KeyError:
            # Player is dead
            pass

    def power_down(self, sid):
        try:
            player = self.tanks[sid]
            player.power -= 2
            player.power = max(player.power, 1)
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
            intersect, _, _ = sphere.intersects_circle(tank.collision_sphere)
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
                    pass
                elif pieces[0] == 'WORLD':
                    pass
                elif pieces[0] == 'PLANET':
                    self.create_planet(Vector(int(pieces[1]), int(pieces[2])),
                                       mass=int(pieces[3]),
                                       radius=int(pieces[4]))
                elif pieces[0] == 'TANK':
                    # Todo get planet number (which is pieces[2], since self.planets is a dict
                    self.create_tank(float(pieces[1]), choice(list(self.planets.values())), sid=f'ai-{i}',
                                     color=pieces[3], is_player=bool(int(pieces[4])))
                    i += 1

    def next_bullet(self, sid):
        self.tanks[sid].selected_bullet = (self.tanks[sid].selected_bullet + 1) % len(self.tanks[sid].bullet_counts)

    def adjust_aim(self, tank: TankObject, monte_carlo: bool = True):
        """

        :param monte_carlo:
        :return:
        """
        test_angle: float = tank.desired_angle
        test_longitude: float = tank.desired_longitude + randint(-10, 10)
        test_power: float = tank.desired_power
        test_roll: float = pi + (
                test_angle + test_longitude) * pi / 180  # Set the roll so that it compensates for the inclination on the planet
        view: Vector = Vector(-sin(test_roll), cos(test_roll))  # Orientation of the phantom bullet.
        previous_distance = self.fire_phantom_gun(SpriteType.WATER_SPRITE, view, test_power, tank,
                                                  tank.position)  # Initial guess, so we have something to compare to.
        if monte_carlo:
            for _ in range(int(1000 * tank.accuracy_multiplier)):
                # Randomize the aim parameters
                test_angle = randint(-15, 195) % 360
                test_longitude = test_longitude
                test_power = float(randint(50, 1000))
                test_roll = pi + (test_angle + test_longitude) * pi / 180
                view = Vector(-sin(test_roll), cos(test_roll))  # Orientation of the phantom bullet.
                new_distance = self.fire_phantom_gun(SpriteType.WATER_SPRITE, view, test_power, tank, tank.position)
                if (new_distance < previous_distance):
                    previous_distance = new_distance
                    deflection = 2.5 * (2 * random() - 1)
                    tank.desired_angle = test_angle + deflection
                    tank.desired_longitude = test_longitude
                    tank.desired_power = test_power
        else:
            # Implement either gradient descend and/or particle swarm optimization
            pass

    def get_nearest_tank_location(self, position: Vector, origin: TankObject):
        current_closest_length = -1
        distance: float = 0
        for _, tank in self.tanks.items():
            if tank != origin and not tank.dead:
                distance = abs(position-tank.position)
                # distance /= 1 - exp(-abs(origin.position - tank.position)**2/250)

        if current_closest_length == -1 or distance < current_closest_length:
            current_closest_length = distance
        # TODO: Wormholes and suicide shots
        return current_closest_length
