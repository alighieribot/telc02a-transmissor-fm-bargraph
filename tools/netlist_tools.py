import json
from pathlib import Path


def load_netlist(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def all_pins(netlist):
    return {f"{ref}.{pin}" for ref, part in netlist["parts"].items() for pin in part["pins"]}


def connected_pins(netlist):
    return [pin for pins in netlist["nets"].values() for pin in pins]


def duplicated_pins(netlist):
    pins = connected_pins(netlist)
    return sorted({pin for pin in pins if pins.count(pin) > 1})


def unknown_pins(netlist):
    return sorted(set(connected_pins(netlist)) - all_pins(netlist))


def unconnected_pins(netlist):
    return sorted(all_pins(netlist) - set(connected_pins(netlist)))


def net_of(netlist, pin):
    for name, pins in netlist["nets"].items():
        if pin in pins:
            return name
    return None


def led_current_amps(r1_ohms):
    return 12.5 / r1_ohms


def led_thresholds_volts(full_scale_volts=1.25, steps=10, step_db=3.0):
    return [full_scale_volts * 10 ** (-step_db * k / 20) for k in range(steps)]


def max_dissipation_watts(supply_volts, led_volts, led_amps, leds=10):
    return (supply_volts - led_volts) * led_amps * leds


def parse_resistance(text):
    text = text.strip().lower()
    if text.endswith("k"):
        return float(text[:-1]) * 1000
    if "k" in text:
        whole, frac = text.split("k")
        return float(f"{whole}.{frac}") * 1000
    return float(text)
