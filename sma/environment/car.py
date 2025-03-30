import logging
from dataclasses import dataclass

from sma.environment.street import Street, Parking
from sma.environment.trafficlight import TrafficLight, TrafficColor


@dataclass
class Car:
    id: int
    position: ((Street | Parking), float)
    max_linear_speed: float
    turning_time_cost: float

    length: float = 1
    target_street: Street | None = None
    marked_for_deletion: bool = False

    is_blocked: bool = False

    _linear_speed: float = 0

    @property
    def street(self):
        return self.position[0]

    def is_parked(self):
        return isinstance(self.position[0], Parking)

    def available_target_streets(self):
        return self.street.available_target_streets()

    def step(self, delta, circuit):

        if not self.is_parked():
            self.drive()
            if circuit.has_car_ahead(self):
                self.stop()
            elif self.is_at_end():
                stoppers = [
                    element
                    for element in self.street.elements_at_end
                    if isinstance(element, TrafficLight) and element.color == TrafficColor.RED
                ]
                if len(stoppers) == 0:
                    self.is_blocked = not self._try_take_next_street(circuit)
                else:
                    self.stop()

            self.position = (
                self.street,
                self.position[1] + self._linear_speed * delta
            )

    def is_at_end(self):
        return self.street.length - self.position[1] < 0

    def _try_take_next_street(self, circuit) -> bool:
        if self.target_street is None:
            self.stop()
            self.marked_for_deletion = len(self.available_target_streets()) == 0
            return False

        if not self.marked_for_deletion:
            if self.target_street is self.street.parallel_street:
                target_position = (self.target_street, self.position[1])
            else:
                length_remainder = self.position[1] - self.street.length
                if self.street.orientation != self.target_street.orientation:
                    length_remainder = 0
                target_position = (self.target_street, length_remainder)

            self.target_street = None
            if (circuit.fits_car_at(self.target_street, target_position[1], self.length)):
                self.position = target_position
                return True
            else:
                self.stop()
                return False

    def can_park(self, circuit):
        return circuit.fits_car_at(self.street.parking, self.position[1], self.length)

    def park(self, circuit):
        if self.is_parked() or not self.street.has_parking:
            logging.info(f"Car {self.id} can't park or is already parked")
            return

        if self.can_park(circuit):
            self.stop()
            self.position = (self.street.parking, self.position[1])

    def unpark(self, circuit) -> bool:
        if not self.is_parked():
            logging.info(f"Car {self.id} is not parked")
            return False

        street = next(
            street
            for street in circuit.streets.values()
            if self.position[0] == street.parking
        )
        if circuit.fits_car_at(street, self.position[1], self.length):
            self.position = (street, self.position[1])
            return True
        else:
            return False

    def stop(self):
        self._linear_speed = 0

    def drive(self):
        self._linear_speed = self.max_linear_speed
