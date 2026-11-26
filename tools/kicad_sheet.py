import re
import uuid
from pathlib import Path

KICAD_SYMBOLS = Path(r"C:\Users\alighieribot\AppData\Local\Programs\KiCad\9.0\share\kicad\symbols")
STUB = 2.54

OUTWARD = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}


def symbol_block(library, name):
    text = (KICAD_SYMBOLS / f"{library}.kicad_sym").read_text(encoding="utf-8")
    start = text.index(f'(symbol "{name}"')
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise ValueError(name)


def embedded_symbol(library, name):
    block = symbol_block(library, name)
    return block.replace(f'(symbol "{name}"', f'(symbol "{library}:{name}"', 1)


def symbol_pins(library, name):
    block = symbol_block(library, name)
    found = re.findall(
        r'\(pin (\w+) \w+\s+\(at ([-\d.]+) ([-\d.]+) (\d+)\)\s+\(length ([\d.]+)\).*?\(number "([^"]*)"',
        block,
        re.S,
    )
    return {number: (float(x), float(y), int(angle)) for _, x, y, angle, _, number in found}


def fmt(value):
    return f"{value:.2f}".rstrip("0").rstrip(".")


def new_uuid(seed, key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}/{key}"))


class SheetBuilder:
    def __init__(self, project, paper="A4"):
        self.project = project
        self.paper = paper
        self.sheet_uuid = new_uuid(project, "sheet")
        self.libraries = {}
        self.items = []
        self.counter = 0

    def next_uuid(self):
        self.counter += 1
        return new_uuid(self.project, f"item{self.counter}")

    def register(self, library, name):
        key = f"{library}:{name}"
        if key not in self.libraries:
            self.libraries[key] = embedded_symbol(library, name)

    def add_wire(self, x1, y1, x2, y2):
        self.items.append(
            f'(wire (pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)})) '
            f'(stroke (width 0) (type default)) (uuid "{self.next_uuid()}"))'
        )

    def add_label(self, text, x, y, angle):
        justify = "left bottom" if angle in (0, 90) else "right bottom"
        self.items.append(
            f'(label "{text}" (at {fmt(x)} {fmt(y)} {angle}) '
            f'(effects (font (size 1.27 1.27)) (justify {justify})) (uuid "{self.next_uuid()}"))'
        )

    def add_symbol(self, library, name, reference, value, footprint, x, y, pin_numbers, field_dx, field_dy, rotation=0):
        self.register(library, name)
        pins = "".join(f'(pin "{number}" (uuid "{self.next_uuid()}")) ' for number in pin_numbers)
        visible = lambda label, text, dy: (
            f'(property "{label}" "{text}" (at {fmt(x + field_dx)} {fmt(y + field_dy + dy)} 0) '
            f'(effects (font (size 1.27 1.27)) (justify left)))'
        )
        hidden = lambda label, text: (
            f'(property "{label}" "{text}" (at {fmt(x)} {fmt(y)} 0) '
            f'(effects (font (size 1.27 1.27)) (hide yes)))'
        )
        self.items.append(
            f'(symbol (lib_id "{library}:{name}") (at {fmt(x)} {fmt(y)} {rotation}) (unit 1) '
            f'(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid "{self.next_uuid()}") '
            f'{visible("Reference", reference, 0)} {visible("Value", value, 2.54)} '
            f'{hidden("Footprint", footprint)} {hidden("Datasheet", "~")} {pins}'
            f'(instances (project "{self.project}" (path "/{self.sheet_uuid}" (reference "{reference}") (unit 1)))))'
        )

    def add_power(self, name, reference, x, y, rotation):
        self.register("power", name)
        self.items.append(
            f'(symbol (lib_id "power:{name}") (at {fmt(x)} {fmt(y)} {rotation}) (unit 1) '
            f'(exclude_from_sim no) (in_bom no) (on_board no) (dnp no) (uuid "{self.next_uuid()}") '
            f'(property "Reference" "{reference}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes))) '
            f'(property "Value" "{name}" (at {fmt(x + 1.27)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (justify left))) '
            f'(property "Footprint" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes))) '
            f'(property "Datasheet" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes))) '
            f'(pin "1" (uuid "{self.next_uuid()}")) '
            f'(instances (project "{self.project}" (path "/{self.sheet_uuid}" (reference "{reference}") (unit 1)))))'
        )

    def render(self, title):
        symbols = "\n".join(self.libraries.values())
        body = "\n".join(self.items)
        return (
            f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0")\n'
            f'(uuid "{self.sheet_uuid}")\n(paper "{self.paper}")\n'
            f'(title_block (title "{title}") (company "UNIFEI TELC02A"))\n'
            f'(lib_symbols\n{symbols}\n)\n{body}\n'
            f'(sheet_instances (path "/" (page "1")))\n(embedded_fonts no)\n)\n'
        )


def pin_endpoint(x, y, pin):
    px, py, angle = pin
    return x + px, y - py, (angle + 180) % 360


def gnd_rotation(outward):
    return {270: 0, 0: 90, 90: 180, 180: 270}[outward]


def vcc_rotation(outward):
    return {90: 0, 180: 90, 270: 180, 0: 270}[outward]


def build_sheet(project, title, netlist, placements, power_nets, power_symbols):
    sheet = SheetBuilder(project)
    pin_to_net = {pin: net for net, pins in netlist["nets"].items() for pin in pins}
    power_counter = 0
    flagged = set()
    for reference, spec in placements.items():
        library, name, footprint, x, y, pin_map, field_dx, field_dy = (
            spec["library"], spec["name"], spec["footprint"], spec["x"], spec["y"],
            spec["pins"], spec["field_dx"], spec["field_dy"],
        )
        value = netlist["parts"][reference]["value"]
        sheet.add_symbol(library, name, reference, value, footprint, x, y, list(pin_map.values()), field_dx, field_dy)
        lib_pins = symbol_pins(library, name)
        for logical_pin, number in pin_map.items():
            net = pin_to_net[f"{reference}.{logical_pin}"]
            ex, ey, outward = pin_endpoint(x, y, lib_pins[number])
            dx, dy = OUTWARD[outward]
            sx, sy = ex + dx * STUB, ey + dy * STUB
            sheet.add_wire(ex, ey, sx, sy)
            if net in power_nets:
                power_counter += 1
                symbol_name = power_symbols[net]
                rotation = gnd_rotation(outward) if net == "GND" else vcc_rotation(outward)
                sheet.add_power(symbol_name, f"#PWR0{power_counter:02d}", sx, sy, rotation)
                if net not in flagged and reference in power_nets[net]:
                    flagged.add(net)
                    power_counter += 1
                    sheet.add_power("PWR_FLAG", f"#FLG0{power_counter:02d}", sx, sy, vcc_rotation(outward))
            else:
                sheet.add_label(net, sx, sy, outward)
    return sheet.render(title)


PROJECT_FILE = '{\n  "meta": {\n    "filename": "%s.kicad_pro",\n    "version": 3\n  }\n}\n'


def write_project(directory, name, content):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.kicad_sch").write_text(content, encoding="utf-8", newline="\n")
    (directory / f"{name}.kicad_pro").write_text(PROJECT_FILE % name, encoding="utf-8", newline="\n")
