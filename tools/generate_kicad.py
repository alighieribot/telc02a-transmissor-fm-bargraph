from pathlib import Path

from kicad_sheet import SheetBuilder, embedded_symbol, write_project
from netlist_tools import load_netlist

ROOT = Path(__file__).resolve().parent.parent

TWO_PINS = {"1": "1", "2": "2"}
RESISTOR = ("Device", "R", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal")
DISC_CAP = ("Device", "C", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm")
POLARIZED_CAP = ("Device", "C_Polarized", "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm")
HEADER_2 = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
HEADER_1 = "Connector_PinHeader_2.54mm:PinHeader_1x01_P2.54mm_Vertical"
AUDIO_JACK_SCH = ("Connector_Audio", "AudioJack2", "Connector_Audio:Jack_3.5mm_CUI_SJ1-3523N_Horizontal")
AUDIO_JACK_TX = ("Connector_Generic", "Conn_01x02", HEADER_2)
INDUCTOR_TX = ("Device", "L", "Inductor_THT:L_Axial_L5.3mm_D2.2mm_P7.62mm_Horizontal_Vishay_IM-1")
TRIMMER_TX = ("Device", "C_Trim", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm")
TO92_WIDE = ("Transistor_BJT", "Q_NPN_CEB", "Package_TO_SOT_THT:TO-92_Inline_Wide")
RADIAL_CAP_2_0 = ("Device", "C_Polarized", "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm")


def part(kind, x, y, pins, field_dx=3.81, field_dy=-1.27, rotation=0):
    library, name, footprint = kind
    return {"library": library, "name": name, "footprint": footprint, "x": x, "y": y,
            "pins": pins, "field_dx": field_dx, "field_dy": field_dy, "rotation": rotation}


TRANSMITTER_PLACEMENT = {
    "J1": part(AUDIO_JACK_TX, 50.8, 60.96, TWO_PINS, -12.7, -6.35, 180),
    "R1": part(RESISTOR, 82.55, 62.23, TWO_PINS),
    "R5": part(RESISTOR, 64.77, 90.17, TWO_PINS),
    "C2": part(RADIAL_CAP_2_0, 82.55, 88.9, {"+": "1", "-": "2"}),
    "C1": part(DISC_CAP, 101.6, 88.9, TWO_PINS),
    "R2": part(RESISTOR, 116.84, 88.9, TWO_PINS),
    "R3": part(RESISTOR, 101.6, 116.84, TWO_PINS),
    "CV1": part(TRIMMER_TX, 129.54, 57.15, TWO_PINS),
    "L1": part(INDUCTOR_TX, 148.59, 58.42, TWO_PINS),
    "Q1": part(TO92_WIDE, 146.05, 101.6,
               {"C": "1", "E": "2", "B": "3"}, 7.62, -1.27),
    "R4": part(RESISTOR, 148.59, 133.35, TWO_PINS),
    "C3": part(DISC_CAP, 175.26, 102.87, TWO_PINS),
    "AE1": part(("Device", "Antenna", HEADER_1), 175.26, 57.15, {"1": "1"}, 3.81, -1.27),
    "C4": part(DISC_CAP, 207.01, 91.44, TWO_PINS),
    "BT1": part(("Device", "Battery", HEADER_2), 236.22, 90.17, {"+": "1", "-": "2"}, -12.7, -1.27),
}

VU_PLACEMENT = {
    "CI1": part(("Driver_LED", "LM3914N", "Package_DIP:DIP-18_W7.62mm_Socket"), 132.08, 93.98,
                {str(n): str(n) for n in range(1, 19)}, 12.7, -22.86),
    "J1": part(AUDIO_JACK_SCH, 83.82, 64.77, {"T": "T", "S": "S"}, -12.7, -6.35),
    "R2": part(RESISTOR, 106.68, 72.39, TWO_PINS),
    "RP1": part(("Device", "R_Potentiometer", "Potentiometer_THT:Potentiometer_Bourns_3386P_Vertical"),
                106.68, 86.36, {"1": "1", "W": "2", "3": "3"}, -12.7, -1.27),
    "R1": part(RESISTOR, 106.68, 109.22, TWO_PINS),
    "C2": part(DISC_CAP, 106.68, 143.51, TWO_PINS),
    "C5": part(POLARIZED_CAP, 129.54, 143.51, {"+": "1", "-": "2"}),
    "BT1": part(("Device", "Battery", HEADER_2), 163.83, 143.51, {"+": "1", "-": "2"}, 3.81, -1.27),
}
for index in range(1, 11):
    VU_PLACEMENT[f"D{index}"] = part(("Device", "LED", "LED_THT:LED_D5.0mm"), 212.09, 60.96 + (index - 1) * 10.16,
                                     {"K": "1", "A": "2"}, -25.4, -1.27)


def add_junction(sheet, x, y):
    sheet.items.append(
        f'(junction (at {x:g} {y:g}) (diameter 0) (color 0 0 0 0) (uuid "{sheet.next_uuid()}"))'
    )


def build_transmitter_sheet(netlist):
    sheet = SheetBuilder("transmissor_te1")
    for ref, spec in TRANSMITTER_PLACEMENT.items():
        value = netlist["parts"][ref]["value"]
        sheet.add_symbol(
            spec["library"], spec["name"], ref, value, spec["footprint"],
            spec["x"], spec["y"], list(spec["pins"].values()), spec["field_dx"], spec["field_dy"],
            spec.get("rotation", 0),
        )
    powers = [
        ("GND", "#PWR001", 60.96, 58.42, 90),
        ("GND", "#PWR008", 64.77, 97.79, 0),
        ("GND", "#PWR003", 101.6, 82.55, 180),
        ("VCC", "#PWR002", 116.84, 82.55, 0),
        ("GND", "#PWR009", 101.6, 123.19, 0),
        ("VCC", "#PWR004", 129.54, 50.8, 0),
        ("VCC", "#PWR005", 148.59, 52.07, 0),
        ("GND", "#PWR010", 148.59, 139.7, 0),
        ("VCC", "#PWR006", 207.01, 85.09, 0),
        ("GND", "#PWR007", 207.01, 97.79, 0),
        ("VCC", "#PWR011", 228.6, 80.01, 0),
        ("PWR_FLAG", "#FLG012", 236.22, 80.01, 0),
        ("GND", "#PWR013", 236.22, 100.33, 0),
        ("PWR_FLAG", "#FLG014", 247.65, 100.33, 180),
    ]
    for name, ref, x, y, rot in powers:
        sheet.add_power(name, ref, x, y, rot)
    wires = [
        (55.88, 58.42, 60.96, 58.42),
        (55.88, 60.96, 72.39, 60.96),
        (72.39, 60.96, 72.39, 58.42),
        (72.39, 58.42, 82.55, 58.42),
        (82.55, 66.04, 82.55, 73.66),
        (82.55, 73.66, 82.55, 85.09),
        (64.77, 73.66, 82.55, 73.66),
        (64.77, 73.66, 64.77, 86.36),
        (64.77, 93.98, 64.77, 97.79),
        (82.55, 92.71, 82.55, 101.6),
        (82.55, 101.6, 101.6, 101.6),
        (101.6, 85.09, 101.6, 82.55),
        (101.6, 92.71, 101.6, 101.6),
        (101.6, 101.6, 101.6, 113.03),
        (101.6, 120.65, 101.6, 123.19),
        (101.6, 101.6, 116.84, 101.6),
        (116.84, 85.09, 116.84, 82.55),
        (116.84, 92.71, 116.84, 101.6),
        (116.84, 101.6, 140.97, 101.6),
        (129.54, 53.34, 129.54, 50.8),
        (129.54, 60.96, 129.54, 82.55),
        (129.54, 82.55, 148.59, 82.55),
        (148.59, 54.61, 148.59, 52.07),
        (148.59, 62.23, 148.59, 82.55),
        (148.59, 82.55, 148.59, 96.52),
        (148.59, 82.55, 175.26, 82.55),
        (175.26, 62.23, 175.26, 82.55),
        (175.26, 82.55, 175.26, 99.06),
        (148.59, 106.68, 148.59, 116.84),
        (148.59, 116.84, 148.59, 129.54),
        (175.26, 106.68, 175.26, 116.84),
        (175.26, 116.84, 148.59, 116.84),
        (148.59, 137.16, 148.59, 139.7),
        (207.01, 87.63, 207.01, 85.09),
        (207.01, 95.25, 207.01, 97.79),
        (228.6, 80.01, 236.22, 80.01),
        (236.22, 80.01, 236.22, 85.09),
        (236.22, 95.25, 236.22, 97.79),
        (236.22, 100.33, 236.22, 97.79),
        (247.65, 97.79, 236.22, 97.79),
        (247.65, 100.33, 247.65, 97.79),
    ]
    for x1, y1, x2, y2 in wires:
        sheet.add_wire(x1, y1, x2, y2)
    junctions = [
        (82.55, 73.66),
        (101.6, 101.6),
        (116.84, 101.6),
        (148.59, 82.55),
        (175.26, 82.55),
        (148.59, 116.84),
        (236.22, 80.01),
        (236.22, 97.79),
    ]
    for x, y in junctions:
        add_junction(sheet, x, y)
    return sheet.render("Transmissor FM PN2222A / BF494 (Entrada P2, Antena Monopolo 20cm, Li-Ion 18650)")


def generate():
    transmitter = load_netlist(ROOT / "netlists" / "transmissor_te1.json")
    write_project(
        ROOT / "kicad" / "transmissor", "transmissor_te1",
        build_transmitter_sheet(transmitter),
    )


if __name__ == "__main__":
    generate()
