from enum import Enum, auto
from itertools import tee
from math import atan2, pi, ceil, e as euler_number
from random import randint

import numpy as np
from socketio import AsyncServer

from .Object import Object
from .SpriteType import SpriteType
from .vector import Vector, Sphere, UnitVector, AngleVector


def pairwise(iterable):
    """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


class PlanetGenerationAlgo(Enum):
    """Determines the noise algorithm used to generate planet terrain"""
    FractalNoise = auto()
    PlanetaryNoise = auto()
    Circular = auto()
    Spiral = auto()


class PlanetGenerationAlgoError(ValueError):
    pass


class PlanetObject(Object):
    def __init__(self, position: Vector, radius: int = 500, planetary_generation_method: PlanetGenerationAlgo = None):
        """
        Generate the Planet Object.
        :param position: Vector representing the center of the planet in game space.
        :param radius: some integer representing the radius of the planet
        :param planetary_generation_method: PlanetGenerationAlgo representing how the planet terrain
        should be generated.
        """
        super().__init__(position, SpriteType.PLANET_SPRITE)
        self.number_of_altitudes = 360 * 2
        self.altitudes: np.ndarray = np.zeros((self.number_of_altitudes,), dtype=int)  # Initialize all heights as 0
        self.sealevel_radius = radius
        self.maximum_altitude = self.sealevel_radius
        self.minimum_altitude = self.sealevel_radius
        self.core_radius = int(.3 * self.sealevel_radius)  # Core starts at 1/3 of the depth of the planet
        self.planetary_generation_method = planetary_generation_method or PlanetGenerationAlgo.PlanetaryNoise
        self.generate_initial_terrain(self.planetary_generation_method)
        self.maximum_altitude_sphere: Sphere = Sphere(position, np.max(self.altitudes))
        self.core_sphere = Sphere(position, self.core_radius)
        self.mass = float(np.sum(self.altitudes))

    def generate_initial_terrain(self, algorithm: PlanetGenerationAlgo) -> None:
        """
        Given an algorithm perform the planetary terrain generation using predefined parameters.
        :param algorithm: PlanetGenerationAlgo representing the algorithm to use.
        :return:
        """
        if algorithm == PlanetGenerationAlgo.FractalNoise:
            return self.generate_noise_fractal_naive(num_iterations=1000, step_size=euler_number)
        elif algorithm == PlanetGenerationAlgo.PlanetaryNoise:
            return self.generate_noise_planetary_method(num_iterations=2000, height_step=2, indices_to_move=0)
        elif algorithm == PlanetGenerationAlgo.Circular:
            return self.generate_circular_terrain()
        elif algorithm == PlanetGenerationAlgo.Spiral:
            return self.generate_spiral_terrain()
        else:
            raise PlanetGenerationAlgoError(f'{algorithm=} is not a value Planet Generation Algorithm.')

    def generate_circular_terrain(self):
        """Generate circular terrain."""
        self.altitudes = self.sealevel_radius * np.ones_like(self.altitudes)

    def generate_spiral_terrain(self):
        """Generate a spiral. Starting at longitude=0, the height of the planet surface at that angle increases by
        one with each step. """
        self.altitudes = self.sealevel_radius / self.number_of_altitudes * np.arange(self.number_of_altitudes)

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
        Generate a planet terrain by grabbing a random portion of the planet (usually half of the planet), then
        increasing or decreasing its height by height_step.
        :param num_iterations: int representing number of times to move part of the terrain
        :param height_step: int representing the number of height units to move selected terrain each iteration
        :param indices_to_move: int representing number of indices to move each iteration. Default is 0, which will
        move half of the planet each iteration.
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
        self.altitudes = self.altitudes * tallest_mount_altitude / (
                self.maximum_altitude - self.minimum_altitude) + self.sealevel_radius
        self.altitudes = self.altitudes.astype(int)

        self.maximum_altitude = np.max(self.altitudes)
        self.minimum_altitude = np.min(self.altitudes)

    def destroy_terrain(self, object_boundary: Sphere):
        """
        Destroy all terrain on the planet that intersects object_boundary.
        :param object_boundary: Sphere representing the boundary of the offending object (usually an explosion).
        """
        exposed_indices, origin = self._exposed_indices(object_boundary)

        for i in exposed_indices:
            angle = 2 * pi * i / self.number_of_altitudes
            direction = UnitVector(angle)
            length = self.altitudes[i]

            intersects, first_intersection, second_intersection = object_boundary.intersects_line(origin, direction)
            if intersects:
                f1: float = abs(first_intersection - self.position)  # length to first intersection
                f2: float = abs(second_intersection - self.position)  # length to second intersection
                if length >= f1:
                    self.altitudes[i] = max(f1, length - f2)
            self.altitudes[i] = max(self.altitudes[i], self.core_radius + 5)  # Don't want to expose the core
            self.changes_queue.append([int(i), int(self.altitudes[i])])

    def generate_terrain(self, object_boundary: Sphere):
        """
        Generates terrain within the explosion radius, which immediately falls down to the planet's surface.
        :param object_boundary: Sphere representing the boundary of the offending object (usually an explosion).
        """
        exposed_indices, origin = self._exposed_indices(object_boundary)

        for i in exposed_indices:
            angle = 2 * pi * i / self.number_of_altitudes
            direction = UnitVector(angle)
            length = self.altitudes[i]

            intersects, first_intersection, second_intersection = object_boundary.intersects_line(origin, direction)
            if intersects:
                f1: float = abs(first_intersection - self.position)  # length to first intersection
                f2: float = abs(second_intersection - self.position)  # length to second intersection
                # Dump either the rest of the circle (if bottom intersection is in planet)
                # or the entirety of the way across the circle (if the entire ray is above the planet)
                self.altitudes[i] += f2 - length if length >= f1 else f2 - f1
            # self.altitudes[i] = max(self.altitudes[i], self.core_radius + 5)  # Don't want to expose the core
            self.changes_queue.append([int(i), int(self.altitudes[i])])

    def get_altitude_at_angle(self, angle: float) -> int:
        """
        Obtain the altitude index underneath a longitude angle.
        :param angle: float representing the angle in degrees of the planet
        :return: int representing the altitude index underneath the given angle.
        """
        # The distances are sample of the height of the planet from the core as we walk around the planet. If we have
        # num distances, then each step is 360deg/num
        degrees_per_altitude_change = 360.0 / self.number_of_altitudes
        # Avoids a weird error where sometimes the index is calculated as negative
        altitude_index = int(angle / degrees_per_altitude_change) % self.number_of_altitudes
        return self.altitudes[altitude_index]

    def get_altitude_under_point(self, point: Vector) -> int:
        """
        Obtain the altitude index underneath a given point.
        :param point: Vector representing a point outside of the planet
        :return: int representing the altitude index underneath the given point.
        """
        direction = point - self.position  # Vector pointing from the center to the outside point.
        angle = atan2(direction.y, direction.x) * 180 / pi  # Calculate the angle of the vector in degrees
        return self.get_altitude_at_angle(angle)

    def get_altitude_index_under_point(self, point: Vector) -> int:
        # TODO: fix the fact that this will never give the indices corresponding to pi/2 and 3pi/2 since
        # their tangent is equal to plus or minus infinity
        degrees_per_altitude_change = 360 / self.number_of_altitudes
        direction = point - self.position  # Vector pointing from the center to the outside point.
        angle = atan2(direction.y, direction.x) * 180 / pi  # Calculate the angle of the vector in degrees
        return int(int(angle) / degrees_per_altitude_change) % self.number_of_altitudes

    def get_surface_vector_at_index(self, altitude_index: int) -> Vector:
        """
        Obtain the vector representing the surface position (in game space) of the planet at altitude_index.
        :param altitude_index: int representing the altitude index to search
        :return: Vector representing the surface position of the planet at altitude index.
        """
        angle = 2 * pi * altitude_index / self.number_of_altitudes
        return self.position + AngleVector(angle=angle,
                                           magnitude=self.altitudes[altitude_index % self.number_of_altitudes])

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

    def intersects(self, object_boundary: Sphere) -> bool:
        """
        Determine whether an offending sphere intersects with the planet surface
        :param object_boundary: Sphere representing the offending object (usually an explosion).
        :return: True if the sphere intersects the planet, otherwise false.
        """
        # If the sphere is within the core, then we can quickly return True
        intersects_core = self.core_sphere.intersects_circle_solid_fast(object_boundary)
        if intersects_core:
            return True
        # If the sphere does not intersect the atmosphere, then we can quickly return False.
        intersects_atmosphere = self.maximum_altitude_sphere.intersects_circle_solid_fast(object_boundary)
        if intersects_atmosphere:
            center = object_boundary.center
            altitude_index = self.get_altitude_index_under_point(center)
            # if abs(center-self.position) - object_boundary.radius < self.get_altitude_under_point(center):
            #     return True

            # Now, we need to check if it intersects the triangles below the point.
            # A triangle has vertices of the planet center and the surface positions at two adjacent altitudes indices
            # We check two triangles back and two triangles forward.

            # vertices = [self.get_surface_vector_at_index((altitude_index + i) % self.number_of_altitudes) for i in
            #             range(-2, 2)]

            # for v0, v1 in pairwise(vertices):
            for i in range(-2, 2):
                current_index = (altitude_index + i) % self.number_of_altitudes
                v0: Vector = self.get_surface_vector_at_index(current_index)
                v1: Vector = self.get_surface_vector_at_index((current_index + 1) % self.number_of_altitudes)
                # print('checking', self.position, v1, v0, object_boundary.center)
                # First make sure none of the points are the same
                # Things crash if the triangle is degenerate (i.e. two points are the same).
                # Then check if the object intersects the triangle
                # if (self.position != v0 != v1 != self.position
                #         and object_boundary.intersects_triangle(self.position, v1, v0)):
                if object_boundary.intersects_triangle(self.position, v1, v0):
                    return True
        return False

    def _exposed_indices(self, object_boundary: Sphere) -> (np.ndarray, Vector):
        """
        Obtain all of the indices that are underneath object_boundary. This is used to accelerate certain planet
        collision checks, by checking only relevant longitude indices.
        :param object_boundary: Sphere representing the offending object (usually an explosion).
        :return: ndarray with all of the exposed indices and a Vector representing the center of the planet
        """
        origin: Vector = self.position  # We will center our coordinate system at the center of the planet
        center: Vector = object_boundary.center  # Center of the offending object
        difference: Vector = center - origin
        r: float = object_boundary.radius  # Radius of the offending object
        h: float = abs(difference)  # Distance between the planet core and the offending object

        angle: float  # Angle from the positive x-axis to the altitude we are adjusting.
        # Angle in radians measuring how far we have to sweep (when centered at the planet core) from the offending
        # object center to its radius. This can be found with a little bit of trigonometry.
        delta_angle: float = abs(atan2(r, h))

        # The number of altitude indices that that angle translates to
        delta_altitude_index = ceil(delta_angle * self.number_of_altitudes / (2 * pi))
        direction: Vector  # Direction from the planet center to surface at an angle
        # Altitude index under the center of the offending object
        altitude_index: int = self.get_altitude_index_under_point(center)

        exposed_indices = (altitude_index + np.arange(-delta_altitude_index,
                                                      delta_altitude_index)) % self.number_of_altitudes
        return exposed_indices, origin
