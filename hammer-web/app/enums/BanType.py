from enum import Enum

class BanType(Enum):
    Warning = 0
    Day1Ban = 1
    Day3Ban = 2
    Day7Ban = 3
    Day14Ban = 4
    Day30Ban = 5
    Day90Ban = 6
    PermanentBan = 7