from enum import Enum, auto


class CameraMode(Enum):
    PLAYER_LOCKED = auto()  # camera is always centered around tank
    PLAYER_UNLOCKED = auto()  # player moves camera manually and does not follow tank
    BULLET_LOCKED = auto()  # camera is centered around fired bullets
    TRANSITION = auto()  # camera is moving in transition
    FIXED = auto()  # put camera in fixed position, locked onto a point instead of an object


control_lock = True
camera_mode = CameraMode.PLAYER_LOCKED

