import logging
import random
from enum import Enum

from autogen_core import RoutedAgent, message_handler, MessageContext, AgentId

from sma.agent.messages import CarAssignationMessage, PlanRequestMessage, PlanResponseMessage, \
    ParkingAssignationMessage, ParkingRequestMessage, ParkingFoundMessage
from sma.config import UNPARK_PROBABILITY
from sma.environment.circuit import Circuit


class State(int, Enum):
    WANDER = 0
    WANTS_TO_PARK = 1
    IDLE = 2
    WANTS_TO_EXIT = 3
    START = 4


class DriverAgent(RoutedAgent):
    def __init__(self):
        super().__init__("driver")
        self.circuit = Circuit.get_instance()
        self.car = None
        self.state = State.START
        self.achieved_parking = False
        self._time_when_started_searching = self.circuit.time
        self._time_when_finished_searching = None
        self._plan = None
        self._last_target_street = None

    @message_handler
    async def handle_plan_response(self, message: PlanResponseMessage, ctx: MessageContext) -> None:
        self._plan = [self.circuit.streets[sid] for sid in message.plan]

    @message_handler
    async def handle_car_assignation(self, message: CarAssignationMessage, ctx: MessageContext) -> None:
        self.car = self.circuit.cars[message.car_id]
        self.circuit.drivers[self.car.id] = self
        logging.info(f"Car {self.car.id} assigned to driver {self.id}")

    @message_handler
    async def handle_parking_assignation(self, message: ParkingAssignationMessage, ctx: MessageContext) -> None:
        if self.state == State.WANTS_TO_PARK:
            await self.runtime.send_message(
                PlanRequestMessage(
                    self.car.street.id,
                    message.street_id
                ),
                AgentId("planner", "default")
            )

    async def act(self):
        if self.car.marked_for_deletion:
            return

        match self.state:
            case State.START:
                await self._start()
            case State.WANTS_TO_PARK:
                await self._try_park()
            case State.WANDER:
                self._wander()
            case State.IDLE:
                self._idle()
            case State.WANTS_TO_EXIT:
                await self._go_to_exit()

    def _set_target_street(self, street):
        self._last_target_street = self.car.target_street
        self.car.target_street = street

    async def _go_to_exit(self):
        if self.car.is_parked():
            if self.car.unpark(self.circuit):
                desired_exit = random.choice([
                    street
                    for street in self.circuit.streets.values()
                    if any(
                        type(element) == str and element.startswith("@end")
                        for element in street.elements_at_end
                    )
                ])
                await self.runtime.send_message(
                    PlanRequestMessage(
                        self.car.street.id,
                        desired_exit.id
                    ),
                    AgentId("planner", "default")
                )
        else:
            self._follow_plan()

    def _follow_plan(self):
        plan = self._plan
        if plan is not None:
            while plan[0] not in self.car.street.available_target_streets():
                plan = plan[1:]
            if len(plan) > 0:
                self._set_target_street(plan[0])
                self._plan = plan[1:]

        if self.car.is_blocked:
            self._wander()

    def _idle(self):
        if self.car.is_parked():
            if random.random() < UNPARK_PROBABILITY:
                self.state = State.WANTS_TO_EXIT

    async def _try_park(self):
        if self.car.is_parked():
            return

        if self._plan is None:
            self._wander()

        else:
            self._follow_plan()

        if self.car.street.has_parking and self.car.can_park(self.circuit):
            self.car.park(self.circuit)
            self.achieved_parking = True
            self._time_when_finished_searching = self.circuit.time
            self.state = State.IDLE
            await self.runtime.send_message(
                ParkingFoundMessage(
                    self.car.street.id,
                    self.car.position[1]
                ),
                AgentId("parker", "default")
            )

    def _wander(self):
        if self.car.is_at_end():
            available_streets = self.car.available_target_streets()

            if self._last_target_street in available_streets:
                available_streets.remove(self._last_target_street)

            turns = random.sample(available_streets, len(available_streets))
            if len(turns) > 0:
                self._set_target_street(turns[0])

    async def _start(self):
        await self.runtime.send_message(
            ParkingRequestMessage(
                self.car.street.id,
                self.car.position[1]
            ),
            AgentId("parker", "default")
        )
        self.state = State.WANTS_TO_PARK

    def time_to_park(self):
        return self._time_when_finished_searching - self._time_when_started_searching
