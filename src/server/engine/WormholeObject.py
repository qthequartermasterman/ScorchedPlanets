from .Object import Object
from dataclasses import dataclass

from .vector import Vector


class WormholeObject(Object):
    def __init__(self, position: Vector, turns_to_live: int, next_wormhole=None):
        super().__init__(position)
        self.turns_before_death: int = turns_to_live
        self.corresponding_wormhole: WormholeObject = next_wormhole
        self.angle: float = 0
        self.radius: float = 80
        self.disabled: bool = False

    def decrement_life(self):
        self.turns_before_death -= 1
        return self.turns_before_death

    def get_json(self):
        return {'angle': self.angle,
                'radius': self.radius,
                }
