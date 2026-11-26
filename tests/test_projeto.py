import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import netlist_tools as nt
from trace_copper import copper_groups

TRANSMITTER = nt.load_netlist(ROOT / "netlists" / "transmissor_te1.json")
VU_METER = nt.load_netlist(ROOT / "netlists" / "vu_meter_lm3915.json")
BOTTOM_LAYER = ROOT / "docs" / "referencias" / "te1" / "extraido" / "transmissor" / "png" / "bottom-layer.png"

PAD_PINS = {
    (235, 72): "C1.1", (310, 72): "R2.1", (452, 88): "CV1.1",
    (601, 85): "L1.1", (723, 342): "C4.1", (843, 387): "BT1.+",
    (235, 192): "C1.2", (253, 303): "C2.-", (310, 312): "R2.2", (310, 357): "R3.1", (452, 420): "Q1.B",
    (452, 206): "CV1.2", (452, 300): "Q1.C", (543, 297): "C3.1", (601, 265): "L1.2", (681, 247): "AE1.1",
    (94, 484): "R5.2", (310, 597): "R3.2", (370, 597): "R4.2", (723, 462): "C4.2", (843, 447): "BT1.-",
    (94, 424): "R5.1", (137, 312): "R1.2", (193, 303): "C2.+",
    (370, 357): "R4.1", (452, 360): "Q1.E", (543, 357): "C3.2",
}
OFF_BOARD_PINS = {"J1.1", "J1.2", "R1.1"}


class NetlistIntegrity(unittest.TestCase):
    def check(self, netlist):
        self.assertEqual(nt.duplicated_pins(netlist), [])
        self.assertEqual(nt.unknown_pins(netlist), [])
        self.assertEqual(nt.unconnected_pins(netlist), [])

    def test_transmitter(self):
        self.check(TRANSMITTER)

    def test_vu_meter(self):
        self.check(VU_METER)


class TransmitterTopology(unittest.TestCase):
    def test_feedback_capacitor_between_collector_and_emitter(self):
        self.assertEqual(nt.net_of(TRANSMITTER, "C3.1"), nt.net_of(TRANSMITTER, "Q1.C"))
        self.assertEqual(nt.net_of(TRANSMITTER, "C3.2"), nt.net_of(TRANSMITTER, "Q1.E"))

    def test_tank_between_supply_and_collector(self):
        for ref in ("L1", "CV1"):
            self.assertEqual(nt.net_of(TRANSMITTER, f"{ref}.1"), "VCC")
            self.assertEqual(nt.net_of(TRANSMITTER, f"{ref}.2"), "COLLECTOR")

    def test_bias_divider_and_p2_audio_input(self):
        self.assertEqual(nt.net_of(TRANSMITTER, "R2.1"), "VCC")
        self.assertEqual(nt.net_of(TRANSMITTER, "R2.2"), "BASE")
        self.assertEqual(nt.net_of(TRANSMITTER, "R3.2"), "GND")
        self.assertEqual(nt.net_of(TRANSMITTER, "J1.1"), "AUDIO_IN")
        self.assertEqual(nt.net_of(TRANSMITTER, "R1.1"), "AUDIO_IN")
        self.assertEqual(nt.net_of(TRANSMITTER, "J1.2"), "GND")
        self.assertEqual(nt.net_of(TRANSMITTER, "R1.2"), "AUDIO")
        self.assertEqual(nt.net_of(TRANSMITTER, "R5.1"), "AUDIO")
        self.assertEqual(nt.net_of(TRANSMITTER, "R5.2"), "GND")
        self.assertEqual(nt.net_of(TRANSMITTER, "C2.+"), "AUDIO")
        self.assertEqual(nt.net_of(TRANSMITTER, "C2.-"), "BASE")
        self.assertNotEqual(nt.net_of(TRANSMITTER, "R1.1"), "VCC")

    def test_p2_attenuator_ratio_and_helical_antenna(self):
        r1 = nt.parse_resistance(TRANSMITTER["parts"]["R1"]["value"])
        r5 = nt.parse_resistance(TRANSMITTER["parts"]["R5"]["value"])
        self.assertAlmostEqual(r5 / (r1 + r5), 1.0 / 11.0, places=4)
        self.assertEqual(TRANSMITTER["parts"]["AE1"]["value"], "Monopolo 15-20cm 20AWG")

    def test_matches_gerber_copper_trace(self):
        traced = {
            frozenset(PAD_PINS[pad] for pad in group if pad in PAD_PINS and PAD_PINS[pad] != "C1.1")
            for group in copper_groups(BOTTOM_LAYER)
        }
        traced.discard(frozenset())
        declared = {
            frozenset(pin for pin in pins if pin not in OFF_BOARD_PINS and pin != "C1.1")
            for pins in TRANSMITTER["nets"].values()
        }
        declared.discard(frozenset())
        self.assertEqual(traced, declared)
        self.assertEqual(nt.net_of(TRANSMITTER, "C1.1"), "GND")
        self.assertEqual(nt.net_of(TRANSMITTER, "C1.2"), "BASE")


class VuMeterDesign(unittest.TestCase):
    def test_led_cathodes_follow_lm3915_pin_order(self):
        pins = ["1", "18", "17", "16", "15", "14", "13", "12", "11", "10"]
        for index, pin in enumerate(pins, start=1):
            self.assertEqual(nt.net_of(VU_METER, f"CI1.{pin}"), nt.net_of(VU_METER, f"D{index}.K"))

    def test_bar_mode_and_reference(self):
        self.assertEqual(nt.net_of(VU_METER, "CI1.9"), "VCC")
        self.assertEqual(nt.net_of(VU_METER, "CI1.3"), "VCC")
        self.assertEqual(nt.net_of(VU_METER, "CI1.2"), "GND")
        self.assertEqual(nt.net_of(VU_METER, "CI1.4"), "GND")
        self.assertEqual(nt.net_of(VU_METER, "CI1.8"), "GND")
        self.assertEqual(nt.net_of(VU_METER, "CI1.6"), nt.net_of(VU_METER, "CI1.7"))
        self.assertEqual(nt.net_of(VU_METER, "R1.1"), "REF")

    def test_led_current_with_selected_r1(self):
        r1 = nt.parse_resistance(VU_METER["parts"]["R1"]["value"])
        self.assertAlmostEqual(nt.led_current_amps(r1), 0.0057, places=4)

    def test_dissipation_within_dip18_limit(self):
        r1 = nt.parse_resistance(VU_METER["parts"]["R1"]["value"])
        power = nt.max_dissipation_watts(VU_METER["supply_volts"][1], 2.0, nt.led_current_amps(r1))
        self.assertLess(power, 0.5)

    def test_twelve_volts_with_10ma_exceeds_limit(self):
        self.assertGreater(nt.max_dissipation_watts(12, 2.0, 0.010), 0.95)

    def test_thresholds_step_three_db(self):
        levels = nt.led_thresholds_volts()
        self.assertEqual(len(levels), 10)
        self.assertAlmostEqual(levels[0], 1.25)
        for higher, lower in zip(levels, levels[1:]):
            self.assertAlmostEqual(20 * math.log10(higher / lower), 3.0, places=6)
        self.assertAlmostEqual(levels[-1], 0.0558, places=4)


class CoilDesign(unittest.TestCase):
    def wheeler_microhenry(self, turns, diameter_in, length_in):
        return turns ** 2 * diameter_in ** 2 / (18 * diameter_in + 40 * length_in)

    def test_four_turns_on_pencil_is_about_0_12_uh(self):
        value = self.wheeler_microhenry(4, 0.276, 0.128)
        self.assertAlmostEqual(value, 0.12, delta=0.01)


if __name__ == "__main__":
    unittest.main()
