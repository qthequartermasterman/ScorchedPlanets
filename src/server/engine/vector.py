from itertools import combinations
from math import cos, sin, sqrt


class Vector:
    x: float
    y: float

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def __abs__(self):
        """Magnitude of the vector"""
        return sqrt(self.x ** 2 + self.y ** 2)

    def __eq__(self, other):
        return self.equals(other)

    def equals(self, other):
        return self.x == other.x and self.y == other.y

    def __mul__(self, other):
        if isinstance(other, Vector):
            return self.x * other.x + self.y * other.y
        else:
            return Vector(other * self.x, other * self.y)
        # try:
        #     return self.x * other.x + self.y * other.y
        # except AttributeError:
        #     return Vector(other * self.x, other * self.y)

    def __rmul__(self, other):
        return self * other

    def __add__(self, other):
        return Vector(other.x + self.x, other.y + self.y)

    def __sub__(self, other):
        return Vector(self.x - other.x, self.y - other.y)

    def __truediv__(self, other):
        return 1 / other * self

    def __neg__(self):
        return Vector(-self.x, -self.y)

    def __repr__(self):
        return f'Vector({self.x}, {self.y})'

    def rotate(self, radians: float):
        """
        Obtain a new vector by rotating self by radians.
        :param radians: float representing the angle to rotate in radians
        :return: a new Vector
        """
        return Vector(cos(radians) * self.x - sin(radians) * self.y,
                      sin(radians) * self.x + cos(radians) * self.y)


def UnitVector(angle: float):
    return Vector(cos(angle), sin(angle))


def AngleVector(angle: float, magnitude: float):
    return Vector(magnitude * cos(angle), magnitude * sin(angle))


class Sphere:
    center: Vector
    radius: float

    def __init__(self, center: Vector, radius: float):
        self.center = center
        self.radius = radius

    def __repr__(self):
        return f'Sphere: center={self.center}, radius={self.radius}'

    def intersects_line(self, origin: Vector, direction: Vector):
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

    def intersects_circle_fast(self, other_sphere) -> bool:
        """
        Determine intersection without getting the points
        :param other_sphere:
        :return:
        """
        # Determine some constants, for easy access
        center1 = self.center
        r1 = self.radius
        center2 = other_sphere.center
        r2 = other_sphere.radius
        distance_between_centers = abs(center2 - center1)
        return distance_between_centers != 0 and r1 + r2 >= distance_between_centers >= abs(r1 - r2)

    def intersects_circle_solid_fast(self, other_sphere) -> bool:
        center1 = self.center
        r1 = self.radius
        center2 = other_sphere.center
        r2 = other_sphere.radius
        return abs(center2 - center1) < max(r1, r2)

    def intersects_circle(self, other_sphere) -> (bool, Vector, Vector):
        """
        Find intersection points of two spheres
        :param other_sphere: Sphere object representing the sphere to check intersections
        :return: (IntersectionExists: bool, FirstIntersectionPoint: Vector, SecondIntersectionPoint: Vector)
        """
        # Determine some constants, for easy access
        center1 = self.center
        r1 = self.radius
        center2 = other_sphere.center
        r2 = other_sphere.radius
        diff_between_centers = center2 - center1
        distance_between_centers = abs(diff_between_centers)

        # Determine if the circles even do intersect. There are four cases:
        # 1. Centers are the same => Cannot intersect (either coincident or one contained in other)
        # 2. Circles are further apart than the sum of their radius => Cannot intersect (too far apart)
        # 3. Circles are close than the absolute value of the difference of radius => Cannot intersect(one inside other)
        # 4. Otherwise => Circles intersect
        # Note that in the 4th case, we can find two sub-cases, where the circles are tangent (and thus intersect once)
        # or where the circles intersect twice. Technically, we could just handle the second sub-case, but we separate
        # them here for computational speed.
        if (distance_between_centers == 0
                or distance_between_centers > r1 + r2
                or distance_between_centers < abs(r1 - r2)
        ):
            # 1. Circles that have same center are either coincident or one is contained within the other
            # OR
            # 2. Circles are too far apart to intersect
            # OR
            # 3. One circle contained in other
            return False, None, None
        # For certain, our circles intercept.
        # Calculate the distance to the intersection area center.
        distance_recip = (1 / distance_between_centers)
        dis_to_area_center = (r1 ** 2 - r2 ** 2 + distance_between_centers ** 2) / (2 * distance_between_centers)
        # Calculate the center of the intersection area
        center_of_intersection_area = center1 + dis_to_area_center * diff_between_centers * distance_recip
        if dis_to_area_center == r1:
            # The two circles are tangent and thus intersect at exactly one point
            # Technically this check is unnecessary, since the below computation will return two equal points.
            # But to save on speed, we can just return the center point, since we know that is the single
            # intersection point
            return True, center_of_intersection_area, center_of_intersection_area
        # Two circles intersect at two points
        height = sqrt(r1 ** 2 - dis_to_area_center ** 2)
        x2 = center_of_intersection_area.x
        y2 = center_of_intersection_area.y
        diff_y = center2.y - center1.y
        diff_x = center2.x - center1.x
        height_times_distance_recip = height * distance_recip
        y_displacement = diff_y * height_times_distance_recip
        x_displacement = diff_x * height_times_distance_recip

        x3 = x2 + y_displacement
        y3 = y2 - x_displacement
        x4 = x2 - y_displacement
        y4 = y2 + x_displacement
        return True, Vector(x3, y3), Vector(x4, y4)

    def intersects_line_segment(self, v0: Vector, v1: Vector) -> bool:
        """
        Check if the circle intersects with line segment between v0 and v1
        :param v0:
        :param v1:
        :return:
        """
        # project the vector v0-center onto the line segment.
        # let d = a + the projection
        # if |DC| is less than the radius, then the circle must intersect the infinite line
        # Additionally, if D is between a and b, then the circle intersects the line in the segment at least once
        ac = self.center - v0
        ab = v1 - v0
        proj: Vector = ((ac * ab) / (ab * ab)) * ab
        d = v0 + proj

        return abs(self.center - d) <= self.radius and abs(proj) <= abs(v1 - v0)

    def intersects_triangle(self, v0, v1, v2):
        # Slow algorithm just checks if any of the line segments intersect.
        # Not terribly slow, but faster algorithms exist, I'm sure.
        return any(self.intersects_line_segment(vert1, vert2) for vert1, vert2 in combinations((v0, v1, v2), 2))

        # This faster algorithm is inspired by the Separating Axis Theorem
        # We will choose 3 projection axes: parallel to the center of the circle to each of the 3 vertices
        # Then if for any of these three tests, the radius (projection of circle) does not intersect with projection of
        # the triangle, then there exists a separating axis.
        # The specifics are bit more complicated to hash out and then prove.
