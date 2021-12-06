from enum import Enum


class FORMAT(Enum):
    MP4 = "mp4"
    JPG = "jpg"
    AVI = "avi"
    PNG = "png"


class Feedback(Enum):
    BORING = -3
    HIT_COUNT = 1
    NEW_COV = 5
    NEW_HANG = 5
    NEW_CRASH = 10
