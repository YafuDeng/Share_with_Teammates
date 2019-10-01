import copy
from dlgo.gotypes import Player
from dlgo import zobrist


class Move:  # handle three types of move: play, pass, resign
    def __init__(self, point=None, is_pass=False, is_resign=False):
        assert (point is not None) ^ is_pass ^ is_resign
        self.point = point
        self.is_play = (self.point is not None)
        self.is_pass = is_pass
        self.is_resign = is_resign

    @classmethod
    def play(cls, point):  # place a stone on the board
        return Move(point=point)

    @classmethod
    def pass_turn(cls):  # this move is passes
        return Move(is_pass=True)

    @classmethod
    def resign(cls):  # resign the current game
        return Move(is_resign=True)


class GoString:  # Go strings are a chaim of connected stones of the same color
    def __init__(self, color, stones, liberties):
        self.color = color
        self.stones = frozenset(stones)
        self.liberties = frozenset(liberties)  # stones and liberties are now immutable frozenset instances

    def without_liberty(self, point):  # replaces the previous remove_liberty method
        new_liberties = self.liberties - set([point])
        return GoString(self.color, self.stones, new_liberties)

    def with_liberty(self, point):
        new_liberties = self.liberties | set([point])  # replaces the previous add_liberty
        return GoString(self.color, self.stones, new_liberties)

    # returns a new Go string containing all stones in both strings
    # since when player place a stones that connects two different strings
    # we need to combine those two strings into one
    def merged_with(self, go_string):
        assert go_string.color == self.color
        combined_stones = self.stones | go_string.stones  # this gives the result of all stones in both strings
        return GoString(
            self.color,
            combined_stones,
            (self.liberties | go_string.liberties) - combined_stones)

    @property
    def num_liberties(self):  # @property makes the function read-only
        return len(self.liberties)  # returns the number of liberties of the point asked

    def __eq__(self, other):  # a "rich comparison" function that can return any value if the two arguments equals
        # it works exactly as a comparison equation but it can be implemented when the outcome is "true"
        # instead of just returning a bool variable "true" or "false"
        return isinstance(other, GoString) and \
            self.color == other.color and \
            self.stones == other.stones and \
            self.liberties == other.liberties


class Board:
    def __init__(self, num_rows, num_cols):  # initialize a board with specific number of row and cols
        self.num_rows = num_rows
        self.num_cols = num_cols
        self._grid = {}
        self._hash = zobrist.EMPTY_BOARD

    def place_stone(self, player, point):
        assert self.is_on_grid(point)
        assert self._grid.get(point) is None
        adjacent_same_color = []
        adjacent_opposite_color = []
        liberties = []
        for neighbor in point.neighbors():  # examine direct neighbors of this point
            if not self.is_on_grid(neighbor):
                continue
            neighbor_string = self._grid.get(neighbor)
            if neighbor_string is None:
                liberties.append(neighbor)
            elif neighbor_string.color == player:
                if neighbor_string not in adjacent_same_color:
                    adjacent_same_color.append(neighbor_string)
            else:
                if neighbor_string not in adjacent_opposite_color:
                    adjacent_opposite_color.append(neighbor_string)
        new_string = GoString(Player, [point], liberties)  # until this line, place_stone remains the same

        for same_color_string in adjacent_same_color:  # you merge any adjacent strings of the same color
            new_string = new_string.merged_with(same_color_string)
        for new_string_point in new_string.stones:
            self._grid[new_string_point] = new_string

        self._hash ^= zobrist.HASH_CODE[point, player]  # next, you apply the hash code for this point and player

        for other_color_string in adjacent_opposite_color:
            # then you reduce liberties of any adjacent strings of the opposite color
            replacement = other_color_string.withou_liberty(point)
            if replacement.num_liberties:
                self._replace_string(other_color_string.without_liberty(point))
            else:
                # if any opposite-color strings now have zero liberties, remove them
                self._remove_string(other_color_string)

    def is_on_grid(self, point):  # check if the point is within the bound of the board
        return 1 <= point.row <= self.num_rows and \
            1 <= point.col <= self.num_cols

    def get(self, point):  # returns the content of a point on the board: Player if a stone on that point, or else None
        string = self._grid.get(point)
        if string is None:
            return None
        return string.color

    def get_go_string(self, point):  # return the entire string of stones at a point if stone is on that point else None
        string = self._grid.get(point)
        if string is None:
            return None
        return string

    def _replace_string(self, new_string):  # a new helper methods updates Go board grid
        for point in new_string.stones:
            self._grid[point] = new_string

    def _remove_string(self, string):
        for point in string.stones:
            for neighbor in point.neighbors():  # remove a string can create liberties for other strings
                neighbor_string = self._grid.get(neighbor)
                if neighbor_string is None:
                    continue
                if neighbor_string is not string:
                    self._replace_string(neighbor_string.with_liberty(point))
            self._grid[point] = None
            # without zobrist hashing, you need to unapply the hash for this move
            self._hash ^= zobrist.HASH_CODE[point, string.color]

    def zobrist_hash(self):
        return self._hash


class GameState:  # this class contains all the rules that will be applied
    def __init__(self, board, next_player, previous, move):
        self.board = board
        self.next_player = next_player
        self.previous_state = previous
        if self.previous_state is None:
            self.previous_states = frozenset()
        else:
            self.previous_states = frozenset(
                previous.previous_states |
                {(previous.next_player, previous.board.zobrist_hash())}
            )
        self.last_move = move

    def apply_move(self, move):  # returns the new GameState after applying the move
        if move.is_play:
            next_board = copy.deepcopy(self.board)
            next_board.place_stone(self.next_player, move.point)
        else:
            next_board = self.board
        return GameState(next_board, self.next_player.other, self, move)

    @classmethod
    def new_game(cls, board_size):
        if isinstance(board_size, int):
            board_size = (board_size, board_size)
        board = Board(*board_size)
        return GameState(board, Player.black, None, None)

    def is_over(self):  # check if the game is over
        if self.last_move is None:
            return False
        if self.last_move.is_resign:
            return True
        second_last_move = self.previous_state.last_move
        if second_last_move is None:
            return False
        return self.last_move.is_pass and second_last_move.is_pass

    def is_move_self_capture(self, player, move):  # copy the board and check the number of liberty afterward
        if not move.is_play:
            return False
        next_board = copy.deepcopy(self.board)
        next_board.place_stone(player, move.point)
        new_string = next_board.get_go_string(move.point)
        return new_string.num_liberties == 0

    @property
    def situation(self):
        return (self.next_player, self.board)

    def does_move_violate_ko(self, player, move):
        if not move.is_play:
            return False
        next_board = copy.deepcopy(self.board)
        next_board.place_stone(player, move.point)
        next_situation = (player.other, next_board.zobrist_hash())
        return next_situation in self.previous_states

    def is_valid_move(self, move):  # wrap up all rules to decide if the next move is valid
        if self.is_over():
            return False
        if move.is_pass or move.is_resign:
            return True
        return (
            self.board.get(move.point) is None and
            not self.is_move_self_capture(self.next_player, move) and
            not self.does_move_violate_ko(self.next_player, move)
        )
