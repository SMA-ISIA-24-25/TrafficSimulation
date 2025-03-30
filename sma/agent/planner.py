import heapq
import math

from autogen_core import RoutedAgent, message_handler, MessageContext

from sma.agent.messages import PlanRequestMessage, PlanResponseMessage
from sma.environment.circuit import Circuit


class PlannerAgent(RoutedAgent):

    def __init__(self):
        super().__init__("planner")
        self.circuit = Circuit.get_instance()

    @message_handler
    async def handle_message(self, message: PlanRequestMessage, _: MessageContext) -> PlanResponseMessage:
        start = self.circuit.streets[message.start_street_id]
        goal = self.circuit.streets[message.end_street_id]
        return PlanResponseMessage(self._make_plan(start, goal))

    def _make_plan(self, start, goal) -> list[int]:
        open_set = [(0, start)]
        came_from = {}
        estimated_costs = {start.id: 0}

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal:
                path = [current]
                while current.id in came_from:
                    current = came_from[current.id]
                    path.append(current)

                return list(reversed([street.id for street in path[:-1]]))

            for neighbor in current.available_target_streets():
                turn_cost = 0 if neighbor.orientation == current.orientation else 1
                cars_on_street = len([car for car in self.circuit.cars.values() if car.street == neighbor])
                estimated_cost = estimated_costs[current.id] + neighbor.length + cars_on_street + turn_cost
                if estimated_cost < estimated_costs.get(neighbor.id, math.inf):
                    came_from[neighbor.id] = current
                    estimated_costs[neighbor.id] = estimated_cost
                    heapq.heappush(open_set, (estimated_cost, neighbor))
