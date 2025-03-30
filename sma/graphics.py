import tkinter as tk

from sma.agent.driver import State
from sma.config import PERIOD, PIXELS_PER_UNIT, MARGIN
from sma.environment.circuit import STREET_UNITS_WIDTH, SimulationHistory
from sma.environment.street import Orientation
from sma.environment.trafficlight import TrafficColor


# Asumimos que Orientation, StreetExtremity, Street, Circuit ya están definidos en tu entorno


class Graphics:
    def __init__(self, simulation_history: SimulationHistory):
        self.simulation_history = simulation_history
        self.tk = tk.Tk()
        self.tk.title("Simulador de Tráfico")
        self.canvas = tk.Canvas(self.tk, width=1000, height=800, bg="white")
        self.offset_x = 0
        self.offset_y = 0

        self._simulation_step = 0

    @property
    def snapshot(self):
        return self.simulation_history.history[self._simulation_step]

    def run(self):
        self.canvas.pack()
        self._render_circuit()
        self.refresh()
        self.tk.mainloop()

    def refresh(self):
        if self._simulation_step < len(self.simulation_history.history):
            self.canvas.after(int(PERIOD * 1000), self.refresh)
            self._render_traffic_lights()
            self._render_walkways()
            self._render_cars()
            self._simulation_step += 1
        else:
            self.tk.destroy()

    def _render_circuit(self):
        street_coords = self.simulation_history.street_coords

        # Normalizar coordenadas a positivo
        all_x = [coord[0] for coord in street_coords.values()]
        all_y = [coord[1] for coord in street_coords.values()]
        min_x = min(all_x)
        min_y = min(all_y)

        self.offset_x = (-min_x if min_x < 0 else 0) + MARGIN
        self.offset_y = (-min_y if min_y < 0 else 0) + MARGIN

        for sid, (x, y) in street_coords.items():
            street = self.simulation_history.streets[int(sid)]
            screen_x = x * PIXELS_PER_UNIT + self.offset_x
            screen_y = y * PIXELS_PER_UNIT + self.offset_y
            dx, dy = street.orientation.value

            if street.has_parking:
                perp_x, perp_y = dy, -dx
                if "PARKING LEFT" in self.simulation_history.graphic_hints.get(sid, {}):
                    perp_x *= -1
                    perp_y *= -1
                parking_screen_x = screen_x + perp_x * PIXELS_PER_UNIT * STREET_UNITS_WIDTH
                parking_screen_y = screen_y + perp_y * PIXELS_PER_UNIT * STREET_UNITS_WIDTH
                self._draw_street(parking_screen_x, parking_screen_y, dx, dy, street.length * PIXELS_PER_UNIT, "blue",
                                  False)

            self._draw_street(screen_x, screen_y, dx, dy, street.length * PIXELS_PER_UNIT, "gray", True)

    def _render_cars(self):
        car_colors = {
            State.WANDER: "black",
            State.WANTS_TO_PARK: "yellow",
            State.IDLE: "white",
            State.WANTS_TO_EXIT: "red"
        }
        self.canvas.delete("car")
        for cid, (x, y) in self.snapshot.cars_coords.items():
            screen_x = x * PIXELS_PER_UNIT + self.offset_x
            screen_y = y * PIXELS_PER_UNIT + self.offset_y
            radius = STREET_UNITS_WIDTH * PIXELS_PER_UNIT / 2
            self.canvas.create_oval(
                screen_x - radius,
                screen_y - radius,
                screen_x + radius,
                screen_y + radius,
                fill=car_colors[self.snapshot.cars_color[cid]],
                tags="car"
            )

    def _render_walkways(self):
        self.canvas.delete("walkway")
        for wid, (x, y) in self.simulation_history.walkways_coords.items():
            screen_x = x * PIXELS_PER_UNIT + self.offset_x
            screen_y = y * PIXELS_PER_UNIT + self.offset_y
            radius = PIXELS_PER_UNIT * 0.25
            walkway_color = self.snapshot.walkways[wid]
            color = {
                TrafficColor.RED: "red",
                TrafficColor.GREEN: "gray"
            }[walkway_color]

            self.canvas.create_rectangle(
                screen_x - radius,
                screen_y - radius,
                screen_x + radius,
                screen_y + radius,
                fill=color,
                outline="black",
                width=2,
                tags="walkway"
            )

    def _render_traffic_lights(self):
        self.canvas.delete("traffic_light")
        for tid, (x, y) in self.simulation_history.traffic_lights_coords.items():
            screen_x = (x - 0.5) * PIXELS_PER_UNIT + self.offset_x
            screen_y = y * PIXELS_PER_UNIT + self.offset_y
            radius = PIXELS_PER_UNIT * 0.33
            color = {
                TrafficColor.RED: "red",
                TrafficColor.GREEN: "green"
            }[self.snapshot.traffic_lights[tid]]
            self.canvas.create_oval(
                screen_x - radius,
                screen_y - radius,
                screen_x + radius,
                screen_y + radius,
                fill=color,
                outline="orange",
                width=4,
                tags="traffic_light"
            )

    def _draw_street(self, x, y, dx, dy, length, color, draw_arrow):
        orientation_arrow = {
            Orientation.NORTH: "↑",
            Orientation.EAST: "→",
            Orientation.SOUTH: "↓",
            Orientation.WEST: "←",
        }

        # Vector perpendicular
        perp_dx, perp_dy = -dy, dx

        # Escalar
        scaled_dx = dx * length
        scaled_dy = dy * length
        perp_dx *= STREET_UNITS_WIDTH * PIXELS_PER_UNIT / 2
        perp_dy *= STREET_UNITS_WIDTH * PIXELS_PER_UNIT / 2

        # Esquinas del rectángulo
        x1 = (x - perp_dx)
        y1 = (y - perp_dy)
        x2 = (x + scaled_dx - perp_dx)
        y2 = (y + scaled_dy - perp_dy)
        x3 = (x + scaled_dx + perp_dx)
        y3 = (y + scaled_dy + perp_dy)
        x4 = (x + perp_dx)
        y4 = (y + perp_dy)

        self.canvas.create_polygon(x1, y1, x2, y2, x3, y3, x4, y4, fill=color)

        if draw_arrow:
            self.canvas.create_text(
                x + scaled_dx / 2,
                y + scaled_dy / 2,
                text=orientation_arrow[Orientation((dx, dy))],
                font=("Arial", 24),
                fill="white"
            )
