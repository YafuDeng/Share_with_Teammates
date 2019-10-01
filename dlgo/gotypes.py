import enum
from collections import namedtuple


class Player(enum.Enum):  # a player is either black or white
    black = 1
    white = 2

    @property
    def other(self):  # switch color after each move
        return Player.black if self == Player.white else Player.white


class Point (namedtuple('Point', 'row col')):  # using tuple to represent points of a Go board
    def neighbors(self):
        return [
            Point(self.row-1, self.col),
            Point(self.row+1, self.col),
            Point(self.row, self.col-1),
            Point(self.row, self.col+1),
        ]
