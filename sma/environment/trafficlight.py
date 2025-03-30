import random
from dataclasses import dataclass
from enum import Enum


class TrafficColor(int, Enum):
    RED = 0
    GREEN = 1


@dataclass
class TrafficLight:
    id: int
    color: TrafficColor
    color_durations: dict

    _counter: int = 0

    @classmethod
    def random(cls, id_):
        return cls(
            id=id_,
            color=random.choice(list(TrafficColor)),
            color_durations={
                TrafficColor.RED: random.randint(1, 8),
                TrafficColor.GREEN: random.randint(6, 15)
            }
        )

    def step(self, delta):
        self._counter += delta

        current_color_duration = self.color_durations[self.color]

        if self._counter >= current_color_duration:
            self._counter -= current_color_duration
            self._change_color()

    def _change_color(self):
        self.color = TrafficColor((self.color.value + 1) % len(TrafficColor))
