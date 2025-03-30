from dataclasses import dataclass


@dataclass
class CarAssignationMessage:
    car_id: int


@dataclass
class PlanRequestMessage:
    start_street_id: int
    end_street_id: int


@dataclass
class PlanResponseMessage:
    plan: list[int]


@dataclass
class ParkingRequestMessage:
    street_id: int
    position: float


@dataclass
class ParkingAssignationMessage:
    street_id: int
    position: float


@dataclass
class ParkingFoundMessage:
    street_id: int
    position: float


@dataclass
class ParkingFreedMessage:
    street_id: int
    position: float
