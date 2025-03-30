from dataclasses import dataclass
from enum import Enum


class Orientation(Enum):
    NORTH = (0, -1)
    EAST = (1, 0)
    SOUTH = (0, 1)
    WEST = (-1, 0)


class StreetExtremity(Enum):
    START = 0
    END = 1


@dataclass
class Parking:
    id: int
    length: float
    orientation: Orientation


@dataclass
class Street:
    id: int
    length: float
    orientation: Orientation
    elements_at_end: list
    has_parking: bool
    parallel_street: int | None = None

    parking: Parking | None = None

    def __deepcopy__(self, memo):
        return Street(
            id=self.id,
            length=self.length,
            orientation=self.orientation,
            elements_at_end=[],
            has_parking=self.has_parking,
            parallel_street=self.parallel_street
        )

    def __str__(self):
        return f"Street {self.id}"

    def __repr__(self):
        return f"Street {self.id}"

    def __post_init__(self):
        self.start = (self, StreetExtremity.START)
        self.end = (self, StreetExtremity.END)
        if self.has_parking:
            self.parking = Parking(id=self.id, length=self.length, orientation=self.orientation)

    def __lt__(self, other):
        return self.id < other.id

    def available_target_streets(self, include_parallel=True):
        street_starts = []
        for element in self.elements_at_end:
            match element:
                case (Street, StreetExtremity.START):
                    street_starts.append(element[0])
        if include_parallel and self.parallel_street is not None:
            street_starts += self.parallel_street.available_target_streets(include_parallel=False)
        return street_starts
