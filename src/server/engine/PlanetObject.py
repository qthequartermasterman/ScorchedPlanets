from enum import Enum, auto
from math import atan2, pi, asin, ceil
from random import randint

import numpy as np
from socketio import AsyncServer

from .Object import Object
from .vector import Vector, Sphere, UnitVector
from .SpriteType import SpriteType


class PlanetGenerationAlgo(Enum):
    """Determines the noise algorithm used to generate planet terrain"""
    FractalNoise = auto()
    PlanetaryNoise = auto()


class PlanetObject(Object):
    def __init__(self, position: Vector, radius: int = 500, step_size: float = 2.718,
                 planetary_generation_method: PlanetGenerationAlgo = None):
        super().__init__(position, SpriteType.PLANET_SPRITE)
        self.number_of_altitudes = 360 * 2
        self.altitudes: np.ndarray = np.zeros((self.number_of_altitudes,), dtype=int)  # Initialize all heights as 0
        self.sealevel_radius = radius
        self.maximum_altitude = self.sealevel_radius
        self.minimum_altitude = self.sealevel_radius
        self.core_radius = int(.3 * self.sealevel_radius)  # Core starts at 1/3 of the depth of the planet
        self.planetary_generation_method = planetary_generation_method or PlanetGenerationAlgo.PlanetaryNoise
        # Only planetary is supported right now
        self.generate_noise_planetary_method(2000, 2, 0)
        self.maximum_altitude_sphere: Sphere = Sphere(position, np.max(self.altitudes))
        self.core_sphere = Sphere(position, self.core_radius)
        self.mass = float(np.sum(self.altitudes))

    def generate_noise_fractal_naive(self, num_iterations: int, step_size: float):
        """
        Generates a procedurally generated planet surface using a simple 1D fractal noise algorithm
        :param num_iterations:
        :param step_size:
        :return:
        """
        pass

    def generate_noise_planetary_method(self, num_iterations: int, height_step: int, indices_to_move: int = 0):
        """

        :param num_iterations:
        :param height_step:
        :param indices_to_move:
        :return:
        """
        # The tallest mountain in the solar system (relative to planet size) is Caloris Montes on Mercury,
        # which is .12% of the radius. .12% however, is /way/ too small for dramatic effect in our game. So we'll
        # multiply it by 100. Sometimes, these hills are a tad /too/ dramatic. But we can work with that.
        tallest_mount_altitude = self.sealevel_radius * .12
        # If we don't specify how much to move this round, we'll adjust half the planet.
        indices_to_move = int(indices_to_move) or int(self.number_of_altitudes / 2)

        # Initialize all heights as 0
        self.maximum_altitude = self.minimum_altitude = 0
        # Pick a random chunk of the planet and shift it up or down. Repeat num_iterations times
        for up_down in np.random.randint(2, size=num_iterations):  # Should this chunk go up or down?
            up_down = int(bool(up_down)) or -1  # If up_down is zero, turn it to negative one
            # Choose which chunk of the planet we will raise/lower. Pick a random angle, then choose indices until
            random_index = randint(0, self.number_of_altitudes)
            indices = np.arange(random_index, random_index + indices_to_move, dtype=np.int32) % self.number_of_altitudes
            # Raise/lower the altitude there.
            self.altitudes[indices] += up_down * height_step

        self.maximum_altitude = np.max(self.altitudes)
        self.minimum_altitude = np.min(self.altitudes)

        # Scale the heights so that mountains are in the right range. Then add sealevel_radius.
        self.altitudes = self.altitudes * tallest_mount_altitude / (self.maximum_altitude - self.minimum_altitude) + self.sealevel_radius
        self.altitudes = self.altitudes.astype(int)

        self.maximum_altitude = np.max(self.altitudes)
        self.minimum_altitude = np.min(self.altitudes)

    def destroy_terrain(self, object_boundary: Sphere):
        origin: Vector = self.position  # We will center our coordinate system at the center of the planet
        center: Vector = object_boundary.center  # Center of the offending object
        difference: Vector = center - origin
        r: float = object_boundary.radius  # Radius of the offending object
        h: float = abs(difference)  # Distance between the planet core and the offending object

        angle: float  # Angle from the positive x-axis to the altitude we are adjusting.
        # Angle in radians measuring how far we have to sweep (when centered at the planet core) from the offending
        # object center to its radius. This can be found with a little bit of trigonometry.
        delta_angle: float = abs(asin(r / h))
        # The number of altitude indices that that angle translates to
        delta_altitude_index = ceil(delta_angle * self.number_of_altitudes / (2 * pi))
        direction: Vector  # Direction from the planet center to surface at an angle
        # Altitude index under the center of the offending object
        altitude_index: int = self.get_altitude_index_under_point(center)

        exposed_indices = (altitude_index + np.arange(-delta_altitude_index,
                                                      delta_altitude_index)) % self.number_of_altitudes
        for i in exposed_indices:
            angle = 2 * pi * i / self.number_of_altitudes
            direction = UnitVector(angle)
            length = self.altitudes[i]

            intersects, first_intersection, second_intersection = object_boundary.Intersects(origin, direction)

            if length > self.core_radius + 5 and intersects and length >= first_intersection:
                self.altitudes[i] = max(first_intersection, length - second_intersection)
            self.altitudes[i] = max(self.altitudes[i], self.core_radius + 5)  # Don't want to expose the core
            self.changes_queue.put(i, int(self.altitudes[i]))

    def get_altitude_at_angle(self, angle: float):
        """

        :param angle:
        :return:
        """
        # The distances are sample of the height of the planet from the core as we walk around the planet. If we have
        # num distances, then each step is 360deg/num
        degrees_per_altitude_change = 360.0 / self.number_of_altitudes
        # Avoids a weird error where sometimes the index is calculated as negative
        altitude_index = int(angle / degrees_per_altitude_change) % self.number_of_altitudes
        return self.altitudes[altitude_index]

    def get_altitude_index_under_point(self, point: Vector):
        """

        :param point:
        :return:
        """
        direction = point - self.position  # Vector pointing from the center to the outside point.
        angle = atan2(direction.y, direction.x) * 180 / pi  # Calculate the angle of the vector in degrees
        return self.get_altitude_at_angle(angle)

    def get_surface_vector_at_index(self, altitude_index: int):
        angle = 2 * pi * altitude_index / self.number_of_altitudes
        return self.position + self.altitudes[altitude_index] * UnitVector(angle)

    def get_slope_at_longitude(self, longitude: float):
        """
        Calculates the angular slope of the planet at a given longitude. Uses a basic difference quotient to calculate
        the linear slope of the terrain at that point, and then uses atan2 to get that as an angle.
        :param longitude: float representing the angle in degrees
        :return: approximate slope of the surface at that longitude
        """
        # The distances are sample of the height of the planet from the core as we walk around the planet. If we have
        # num distances, then each step is 360deg/num
        degrees_per_altitude_change = 360.0 / self.number_of_altitudes
        # Avoids a weird error where sometimes the index is calculated as negative
        altitude_index = int(longitude / degrees_per_altitude_change) % self.number_of_altitudes

        # Use a central difference quotient. This doesn't need to be perfect.
        difference: Vector = self.get_surface_vector_at_index(altitude_index + 1) - self.get_surface_vector_at_index(
            altitude_index - 1)
        return atan2(difference.y, difference.x) * 180 / pi

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
                           'core_radius': self.core_radius,
                           'number_of_altitudes': self.number_of_altitudes,
                           'sealevel_radius': self.sealevel_radius,
                           'altitudes': [int(a) for a in list(self.altitudes)]
                           },
                          *args, **kwargs)
