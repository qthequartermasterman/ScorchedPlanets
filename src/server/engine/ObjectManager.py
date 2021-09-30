from typing import List, Dict

from socketio import AsyncServer

from .BulletObject import BulletObject
from .Config import ConfigData, gravity_constant
from .PlanetObject import PlanetObject
from .SpriteType import SpriteType
from .TankObject import TankObject
from .vector import Vector


class ObjectManager:
    def __init__(self):
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

    def create_tank(self, longitude: float, home_planet: PlanetObject, sid: str, color: str = '') -> TankObject:
        """
        Create a new Tank
        :param longitude: float longitude of the tank (angle relative to the planet)
        :param home_planet: PlanetObject of the home planet
        :param color: string representing the color hue of the tank
        :param sid: string representing the
        :return:
        """
        tank = TankObject(longitude=longitude, planet=home_planet, color=color)
        self.tanks[sid] = tank
        return tank

    def create_bullet(self, bullet_sprite: SpriteType, position: Vector, trail_color: str = '') -> BulletObject:
        """

        :param bullet_sprite:
        :param position:
        :param trail_color:
        :return:
        """
        pass

    def create_phantom_bullet(self, bullet, position, velocity, owner) -> float:
        """

        :param bullet:
        :param position:
        :param velocity:
        :param owner:
        :return:
        """

    def move(self):
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
            print('Bullet acceleration:', bullet.acceleration, abs(bullet.acceleration))
            bullet.move()

        for sid, tank in self.tanks.items():
            old_position: Vector = tank.position
            tank.think()
            tank.move()

        # TODO: Do object collision detection and response
        # TODO: Remove dead objects from the lists so we don't have to worry about them in the future.

    def calculate_gravity(self, oldpos) -> Vector:
        pass

    def at_world_edge(self, oldpos) -> bool:
        pass

    async def send_objects_initial(self, sio: AsyncServer, *args, **kwargs):
        for planet in self.planets.values():
            await planet.emit_initial(sio, *args, **kwargs)
        for user in self.users:
            await user.emit_initial(self.tanks, sio, *args, **kwargs)

    async def send_updates(self, sio: AsyncServer, *args, **kwargs):
        # await sio.emit('serverTellPlayerMove', [visibleCells, visibleFood, visibleMass, visibleVirus], room=sid)
        for planet in self.planets.values():
            await planet.emit_changes(sio, *args, **kwargs)

        for user in self.users:
            await user.emit_changes(self.tanks, sio, *args, **kwargs)

        for u in self.users:
            # center the view if x/y is undefined, this will happen for spectators
            u.x = u.x or ConfigData.gameWidth / 2
            u.y = u.y or ConfigData.gameHeight / 2

            def user_mapping_function(f):
                if f.id != u.id:
                    return {'id': f.id,
                            'x': f.x,
                            'y': f.y,
                            'hue': f.hue,
                            'name': f.name
                            }
                else:
                    return {'x': f.x,
                            'y': f.y,
                            'hue': f.hue,
                            'name': f.name
                            }

            user_transmit = [user_mapping_function(x) for x in self.users]
            sid = self.sockets[u.id]
            await sio.emit('serverTellPlayerMove', [user_transmit, [], [], []], room=sid)

    def strafe_right(self, sid):
        self.tanks[sid].strafe_right = True

    def strafe_left(self, sid):
        self.tanks[sid].strafe_left = True

    def remove_player(self, sid):
        del self.tanks[sid]
        for i in range(len(self.users)):
            if self.users[i].id == sid:
                del self.users[i]