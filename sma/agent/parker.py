from autogen_core import RoutedAgent, message_handler, MessageContext

from sma.agent.messages import ParkingRequestMessage, ParkingAssignationMessage, ParkingFoundMessage, \
    ParkingFreedMessage
from sma.environment.circuit import Circuit


class ParkerAgent(RoutedAgent):
    def __init__(self):
        super().__init__("parker")
        self.circuit = Circuit.get_instance()
        self.known_spots = []
        self.requesters_queues = []
        self.assigned_spots = []

    @message_handler
    async def handle_parking_request(self, message: ParkingRequestMessage, ctx: MessageContext) -> None:
        self.requesters_queues.append(ctx.sender)
        self._assign_spots()

    @message_handler
    async def handle_parking_found(self, message: ParkingFoundMessage, ctx: MessageContext) -> None:
        self.assigned_spots = [
            assigned_spot
            for assigned_spot
            in self.assigned_spots
            if assigned_spot[0] != ctx.sender
        ]
        affected_assignments = [
            assigned_spot
            for assigned_spot
            in self.assigned_spots
            if collide(assigned_spot[1], message) and assigned_spot[0] != ctx.sender
        ]
        self.assigned_spots = [
            assigned_spot
            for assigned_spot
            in self.assigned_spots
            if assigned_spot not in affected_assignments
        ]
        self.requesters_queues += [
            assigned_spot[0]
            for assigned_spot
            in affected_assignments
        ]
        self._assign_spots()

    @message_handler
    async def handle_parking_freed(self, message: ParkingFreedMessage, ctx: MessageContext) -> None:
        self.known_spots.append(message)
        self._assign_spots()

    def _assign_spots(self):
        matches_n = min(len(self.known_spots), len(self.requesters_queues))
        for i in range(matches_n):
            recipient = self.requesters_queues[0]
            spot = self.known_spots[0]

            recipient.send(ParkingAssignationMessage(spot.street_id, spot.position))
            self.assigned_spots.append((recipient, spot))

            self.requesters_queues = self.requesters_queues[1:]
            self.known_spots = self.known_spots[1:]


def collide(spot1, spot2):
    return (
            spot1.street_id == spot2.street_id
            and abs(spot1.position - spot2.position) < 1
    )
