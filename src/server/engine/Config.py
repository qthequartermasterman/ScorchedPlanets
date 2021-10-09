import json
from dataclasses import dataclass
from typing import Dict


@dataclass
class Config:
    host: str
    port: int
    logpath: str
    foodMass: int
    fireFood: int
    limitSplit: int
    defaultPlayerMass: int
    virus: Dict
    gameWidth: int
    gameHeight: int
    adminPass: str
    gameMass: int
    maxFood: int
    maxVirus: int
    slowBase: float
    logChat: int
    networkUpdateFactor: int
    maxHeartbeatInterval: int
    foodUniformDisposition: bool
    virusUniformDisposition: bool
    newPlayerInitialPosition: str
    massLossRate: int
    minMassLoss: int
    mergeTimer: int
    sqlinfo: Dict

    def __getitem__(self, item):
        return self.__getattribute__(item)


ConfigData: Config
with open('../../config.json') as f:
    ConfigData = Config(**json.load(f))

turns_enabled: bool = False  # Set False for debug
gravity_constant: float = 500000  # Gravity Constant in Newton's Law of Universal Gravitation
