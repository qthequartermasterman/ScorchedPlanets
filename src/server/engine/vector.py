from dataclasses import dataclass
from math import cos, sin, sqrt

import numpy as np


class Vector(np.ndarray):
    def __new__(cls, x, y, *args, **kwargs):
        obj = super().__new__(cls, (2,), *args, **kwargs)
        obj[0] = x
        obj[1] = y
        return obj

    @property
    def x(self):
        return self[0]

    @property
    def y(self):
        return self[1]

    def __abs__(self):
        """Magnitude of the vector"""
        return np.sqrt(self.dot(self))

    def __hash__(self):
        return hash((self.x, self.y))

    def __eq__(self, other):
        return np.allclose(self, other)


class UnitVector(Vector):
    """Vector with unit length"""

    def __init__(self, angle: float, dtype=float):
        """

        :param angle: Angle of the vector from the positive x-axis in radians
        :param dtype:
        """
        super().__init__(cos(angle), sin(angle), dtype=dtype)


@dataclass
class Sphere:
    center: Vector
    radius: float

    def Intersects(self, origin: Vector, direction: Vector):
        """
        Determines whether the sphere intersects with a given line defined by an origin (point on line) and direction
        (all the points in that direction)

        TODO: Determine whether this is fast enough for our purposes, or if this is faster:
        https://math.stackexchange.com/a/2035466/781590

        :param origin: Vector representing some point in space. This is some point on the line
        :param direction: Vector pointing parallel to the line. All points on line are the origin plus some scalar times
        the direction
        :return: (IntersectionExists: bool, FirstIntersectionPoint: Vector, SecondIntersectionPoint: Vector)
        """
        try:
            m = direction.y / direction.x
        except ZeroDivisionError:
            return self._intersects_vertical_line(origin)
        b = origin.y - m * origin.x
        x0 = self.center.x
        y0 = self.center.y
        r = self.radius

        diff = b - y0  # This subtraction shows up frequently. This is just so we do not need to repeat it.

        # Coefficients of the substituted equation in terms of x. When expanded, it forms a quadratic equation on x.
        coefficient_a = 1 + m ** 2
        # Technically, the B coefficient is twice this quantity, but we will be factoring out a 2 of everything else
        # later on.
        coefficient_b = -x0 + m * diff
        # Technically, the C coefficient is twice this quantity, but we will be factoring out a 2 of everything else
        # later on.
        coefficient_c = x0 ** 2 + diff ** 2 - r ** 2

        # Again, the discriminant should be $b^2-4ac$, but we can simplify the quadratic equation in this case by
        # factoring out the aforementioned 2
        discriminant = coefficient_b ** 2 - coefficient_a * coefficient_c
        if discriminant < 0:  # There are no real solutions, so the line and circle do not intersect on the plane
            return False, None, None
        elif discriminant == 0:  # The line is tangent and there is one real solution
            x = -coefficient_b / coefficient_a
            y = m * x + b
            tangent_point = Vector(x, y)
            return True, tangent_point, tangent_point
        else:  # The discriminant is positive, so there are two real solutions and the line is secant
            x1 = (-coefficient_b + sqrt(discriminant)) / coefficient_a
            x2 = (-coefficient_b - sqrt(discriminant)) / coefficient_a
            y1 = m * x1 + b
            y2 = m * x2 + b
            points = (Vector(x1, y1), Vector(x2, y2))
            first = 0 if abs(points[0] - origin) < abs(points[1] - origin) else 1
            return True, points[first], points[not first]

    # TODO Rename this here and in `Intersects`
    def _intersects_vertical_line(self, origin):
        """
        When dealing with vertical lines, we need to be a bit more clever.
        Use the equation of a circle in the plane, and solve for y, using the x-coordinate of the line as x
        :param origin:
        :return:
        """
        x0 = self.center.x
        y0 = self.center.y
        r = self.radius
        x = origin.x
        if abs(x - x0) >= r:
            return False, None, None

        inside_sqrt = r ** 2 - (x - x0) ** 2
        points = Vector(x, y0 + sqrt(inside_sqrt)), Vector(x, y0 - sqrt(inside_sqrt))
        first = 0 if abs(points[0] - origin) < abs(points[1] - origin) else 1
        return True, points[first], points[not first]
