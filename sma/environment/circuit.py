import logging
import random
from dataclasses import dataclass
from functools import cached_property

from autogen_core import AgentId

from sma.agent.messages import CarAssignationMessage
from sma.config import MAX_CARS
from sma.environment.car import Car
from sma.environment.street import Street, Orientation, StreetExtremity
from sma.environment.trafficlight import TrafficLight, TrafficColor

STREET_UNITS_WIDTH = 0.5
FIXED_DELTA = 1 / 60


@dataclass
class SimulationSnapshot:
    traffic_lights: dict[int, TrafficColor]
    walkways: dict[int, TrafficColor]
    cars_coords: dict[int, tuple[float, float]]
    cars_parked: set[int]
    cars_color: dict[int, int]


@dataclass
class SimulationHistory:
    streets: dict[int, Street]
    traffic_lights_coords: dict[int, tuple[float, float]]
    walkways_coords: dict[int, tuple[float, float]]
    street_coords: dict[int, tuple[float, float]]
    history: list[SimulationSnapshot]
    graphic_hints: dict[int, str]
    stats = {}


class Circuit:

    def __init__(
            self,
            streets: dict[int, Street],
            entry_points: set[int],
            traffic_lights: dict[int, TrafficLight],
            walkways: dict[int, TrafficLight],
            cars: dict[int, Car],
            graphic_hints: dict[int, str]
    ):
        self.streets = streets
        self.entry_points = entry_points
        self.traffic_lights = traffic_lights
        self.walkways = walkways
        self.cars = cars
        self.graphic_hints = graphic_hints
        self._car_counter = 0
        self.agent_runtime = None
        self.history = SimulationHistory(
            streets,
            self.traffic_light_coords,
            self.walkway_coords,
            {},
            [],
            graphic_hints
        )
        self.drivers = {}
        self.time = 0

    def set_agent_runtime(self, agent_runtime):
        self.agent_runtime = agent_runtime
        logging.info(f"Agent runtime set")

    @classmethod
    def load_json(cls, data):
        entry_points = set()
        graphic_hints = {}
        for street_obj in data:
            street_obj["orientation"] = Orientation[street_obj["orientation"]]
            if street_obj.get("is_entry_point", False):
                entry_points.add(street_obj["id"])
                del street_obj["is_entry_point"]

            if street_graphic_hints := street_obj.get("graphic_hint"):
                graphic_hints[street_obj["id"]] = street_graphic_hints
                del street_obj["graphic_hint"]

        streets = {
            street["id"]: Street(**street)
            for street in data
        }

        references = set(sum([street["elements_at_end"] for street in data], []))

        traffic_lights = {
            id_: TrafficLight.random(id_)
            for id_
            in [
                int(ref.split(" ")[1])
                for ref
                in references
                if ref.startswith("@traffic_light")
            ]
        }

        walkways = {
            id_: TrafficLight.random(id_)
            for id_
            in [
                int(ref.split(" ")[1])
                for ref
                in references
                if ref.startswith("@walkway")
            ]
        }

        logging.info(f"streets loaded: {len(streets)}")
        logging.info(f"    with graphic hints: {len(graphic_hints)}")
        logging.info(f"traffic lights: {len(traffic_lights)}")
        logging.info(f"walkways: {len(walkways)}")

        logging.info("Resolving references...")
        resolvers_catalog = {
            "@traffic_light": lambda _id: traffic_lights[_id],
            "@walkway": lambda _id: walkways[_id],
            "@street_start": lambda _id: streets[_id].start,
            "@street_end": lambda _id: streets[_id].end,
            "@end": lambda _id: f"@end {_id}"
        }

        for street in streets.values():
            if street.parallel_street is not None:
                street.parallel_street = streets[street.parallel_street]

            resolved_elements = []
            for element in street.elements_at_end:
                ref_parts = element.split(" ")
                catalog = resolvers_catalog.get(ref_parts[0])
                if catalog is not None:
                    resolved_elements.append(
                        catalog(int(ref_parts[1]))
                    )

            street.elements_at_end = resolved_elements

        circuit_holder.append(
            cls(
                streets=streets,
                traffic_lights=traffic_lights,
                walkways=walkways,
                cars={},
                entry_points=entry_points,
                graphic_hints=graphic_hints
            )
        )

    @staticmethod
    def get_instance():
        return circuit_holder[0]

    @cached_property
    def street_coords(self):
        logging.info("Computing street coordinates...")
        street_coords = {}  # street.id -> (x, y)
        visited = set()

        start_street = self.streets[1]
        queue = [(start_street, (0, 0))]
        street_coords[start_street.id] = (0, 0)

        while queue:
            current, (x, y) = queue.pop(0)
            if current.id in visited:
                continue
            visited.add(current.id)

            street_coords[current.id] = (x, y)

            dx, dy = current.orientation.value
            end_x = x + dx * current.length
            end_y = y + dy * current.length

            for element in current.elements_at_end:
                match element:
                    case (Street, StreetExtremity.START):
                        queue.append((element[0], (end_x, end_y)))
                    case (Street, StreetExtremity.END):
                        dx, dy = element[0].orientation.value
                        start_x = end_x - dx * element[0].length
                        start_y = end_y - dy * element[0].length
                        queue.append((element[0], (start_x, start_y)))

            if current.parallel_street is not None:
                hints_of_parallel = [
                    hint
                    for hint
                    in self.graphic_hints.get(current.id, [])
                    if hint.startswith("PARALLEL")
                ]
                if len(hints_of_parallel) == 1:
                    offset_direction = Orientation[
                        hints_of_parallel[0].split(" ")[1]
                    ]

                    dx, dy = offset_direction.value
                    queue.append((current.parallel_street, (x + dx * STREET_UNITS_WIDTH, y + dy * STREET_UNITS_WIDTH)))
        return street_coords

    def _final_element_coords(self, collection):
        elements_coords = {}
        for element in collection:
            street = next(street for street in self.streets.values() if element in street.elements_at_end)
            start_x, start_y = self.street_coords[street.id]
            dx, dy = street.orientation.value
            elements_coords[element.id] = (
                start_x + dx * (street.length - 0.5),  # quitar una unidad para que se quede en la calle
                start_y + dy * (street.length - 0.5)
            )
        return elements_coords

    def car_coords(self):
        car_coords = {}
        for car in self.cars.values():
            street = car.position[0]
            start_x, start_y = self.street_coords[street.id]
            dx, dy = street.orientation.value

            car_coords[car.id] = (
                start_x + dx * (car.position[1]),  # quitar una unidad para que se quede en la calle
                start_y + dy * (car.position[1])
            )
            if car.is_parked():
                perp_x, perp_y = dy, -dx
                if "PARKING LEFT" in self.graphic_hints.get(street.id, {}):
                    perp_x *= -1
                    perp_y *= -1
                parking_offset_x = perp_x * STREET_UNITS_WIDTH if car.is_parked() else 0
                parking_offset_y = perp_y * STREET_UNITS_WIDTH if car.is_parked() else 0
                car_coords[car.id] = (
                    car_coords[car.id][0] + parking_offset_x,
                    car_coords[car.id][1] + parking_offset_y
                )
        return car_coords

    @cached_property
    def traffic_light_coords(self):
        return self._final_element_coords(self.traffic_lights.values())

    @cached_property
    def walkway_coords(self):
        return self._final_element_coords(self.walkways.values())

    def has_car_ahead(self, car, safe_distance=0.05):
        for other in self.cars.values():
            if other == car or other.street != car.street:
                continue

            front_other = other.position[1] + other.length / 2
            rear_other = other.position[1] - other.length / 2
            front_car = car.position[1] + car.length / 2
            # if rear_other > front_car and rear_other - front_car < safe_distance:
            if front_car < front_other and rear_other - front_car < safe_distance:
                return True
        return False

    def fits_car_at(self, street, point, car_length):
        front = point + car_length / 2
        rear = point - car_length / 2

        for other in self.cars.values():
            if other.street != street:
                continue
            other_front = other.position[1] + other.length / 2
            other_rear = other.position[1] - other.length / 2

            if front >= other_rear and rear <= other_front:
                return False
        return True

    async def step(self, total_delta):
        while total_delta > 0:
            delta = min(total_delta, FIXED_DELTA)
            total_delta -= delta

            for traffic_light in self.traffic_lights.values():
                traffic_light.step(delta)

            for walkway in self.walkways.values():
                walkway.step(delta)

            for car in self.cars.values():
                if not car.marked_for_deletion:
                    car.step(delta, self)

            self.cars = {
                id_: car
                for id_, car in self.cars.items()
                if not car.marked_for_deletion
            }

            spawn_probability = 0.3
            if len(self.cars) < MAX_CARS and random.random() < spawn_probability:
                await self.spawn_car()

            for agent in self.drivers.values():
                await agent.act()

            self.time += delta

    def finish(self):
        total_parked = len([agent for agent in self.drivers.values() if agent.achieved_parking])
        self.history.stats = {
            "time": self.time,
            "total_cars": len(self.cars),
            "cars_parked": total_parked,
            "average_parking_time": sum(
                agent.time_to_park()
                for agent
                in self.drivers.values()
                if agent.achieved_parking
            ) / total_parked
        }

    async def spawn_car(self):
        shuffled_entry_points = [self.streets[entry_point] for entry_point in self.entry_points]
        random.shuffle(shuffled_entry_points)

        car_length = 1
        for entry_point in shuffled_entry_points:
            if self.fits_car_at(entry_point, 0, car_length):
                car = Car(
                    id=self._car_counter,
                    position=(entry_point, 0.0),
                    max_linear_speed=1,
                    turning_time_cost=1,
                    length=car_length
                )
                self.cars[car.id] = car

                await self.agent_runtime.send_message(
                    CarAssignationMessage(car.id),
                    AgentId("driver", str(car.id))
                )
                self._car_counter += 1

                break

    def get_history(self):
        self.history.street_coords = self.street_coords
        return self.history

    def take_snapshot(self):
        self.history.history.append(
            SimulationSnapshot(
                traffic_lights={
                    id_: traffic_light.color
                    for id_, traffic_light in self.traffic_lights.items()
                },
                walkways={
                    id_: walkway.color
                    for id_, walkway in self.walkways.items()
                },
                cars_coords=self.car_coords(),
                cars_parked=set(car.id for car in self.cars.values() if car.is_parked()),
                cars_color={
                    agent.car.id: agent.state
                    for agent in self.drivers.values()
                    if agent.car is not None and not agent.car.marked_for_deletion
                }
            )
        )


circuit_holder = []
