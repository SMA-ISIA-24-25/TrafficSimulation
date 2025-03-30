import argparse
import asyncio
import json
import logging
from enum import Enum

from autogen_core import SingleThreadedAgentRuntime

from sma.agent.driver import DriverAgent
from sma.agent.parker import ParkerAgent
from sma.agent.planner import PlannerAgent
from sma.config import SIMULATION_DELTA, SECONDS, SECONDS_PRE_SIMULATION
from sma.environment.circuit import Circuit, SimulationHistory, SimulationSnapshot
from sma.graphics import Graphics

# disable logging
logging.disable(logging.CRITICAL)

STEPS = int(SECONDS / SIMULATION_DELTA)
STEPS_PRE_SIMULATION = int(SECONDS_PRE_SIMULATION / SIMULATION_DELTA)


async def simulation():
    circuit = Circuit.get_instance()

    agent_runtime = SingleThreadedAgentRuntime()

    await DriverAgent.register(
        agent_runtime,
        "driver",
        lambda: DriverAgent()
    )
    await ParkerAgent.register(
        agent_runtime,
        "parker",
        lambda: ParkerAgent()
    )
    await PlannerAgent.register(
        agent_runtime,
        "planner",
        lambda: PlannerAgent()
    )

    agent_runtime.start()
    circuit.set_agent_runtime(agent_runtime)

    logging.info(f"Start simulation")
    for i in range(STEPS_PRE_SIMULATION):
        await circuit.step(SIMULATION_DELTA)

    for i in range(STEPS):
        await circuit.step(SIMULATION_DELTA)
        circuit.take_snapshot()

    logging.info(f"End simulation: number of steps: {STEPS}")
    circuit.finish()


def display_simulation(history):
    Graphics(history).run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("map", type=str, help="Map file")
    parser.add_argument("--output", type=str, help="Output file")
    parser.add_argument("--input", type=str, help="Input file")

    args = parser.parse_args()

    if args.output is None:
        args.output = "output.json"

    circuit_data = json.load(open(args.map))
    Circuit.load_json(circuit_data)
    circuit = Circuit.get_instance()

    if args.input is None:
        asyncio.run(simulation())
        history = circuit.get_history()
        with open(args.output, "w") as f:

            def to_dict(o):
                if isinstance(o, Enum):
                    return o.value
                if hasattr(o, "__dict__"):
                    return o.__dict__


            history.streets = []
            json.dump(history, f, default=to_dict)
    else:
        with open(args.input) as f:
            data = json.load(f)
            stats = data["stats"]
            del data["stats"]
            history = SimulationHistory(**data)
            history.history = [
                SimulationSnapshot(**snapshot)
                for snapshot
                in history.history
            ]

    history.streets = circuit.streets
    print(json.dumps(history.stats, indent=2))
    Graphics(history).run()
