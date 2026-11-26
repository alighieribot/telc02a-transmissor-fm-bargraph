import re
import subprocess
import tempfile
import xml.etree.ElementTree as ElementTree
import zlib
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
KICAD_ROOT = Path(r"C:\Users\alighieribot\AppData\Local\Programs\KiCad\9.0")
KICAD_CLI = KICAD_ROOT / "bin" / "kicad-cli.exe"
FOOTPRINTS_DIR = KICAD_ROOT / "share" / "kicad" / "footprints"
SCH_PATH = ROOT / "kicad" / "transmissor" / "transmissor_te1.kicad_sch"
PCB_PATH = ROOT / "kicad" / "transmissor" / "transmissor_te1.kicad_pcb"
TONER_PDF_PATH = ROOT / "kicad" / "transmissor" / "transmissor_te1_toner_transfer.pdf"
TONER_MIRROR_PDF_PATH = ROOT / "kicad" / "transmissor" / "transmissor_te1_toner_transfer_mirror.pdf"
MONTAGEM_PDF_PATH = ROOT / "kicad" / "transmissor" / "transmissor_te1_montagem_top.pdf"

ORIGIN_X = 100.0
ORIGIN_Y = 100.0
BOARD_W = 46.0
BOARD_H = 30.0
TILE_COLS = 4
TILE_ROWS = 4
TILE_GAP_MM = 12.0


def pt(x_mm, y_mm):
    return pcbnew.VECTOR2I(pcbnew.FromMM(ORIGIN_X + x_mm), pcbnew.FromMM(ORIGIN_Y + y_mm))


COMPONENT_LAYOUT = {
    "J1": {"x": 3.5, "y": 5.5, "deg": 0.0, "ref_offset": (0.0, -2.5)},
    "R5": {"x": 3.5, "y": 14.5, "deg": -90.0, "ref_offset": (0.0, -2.2)},
    "R1": {"x": 7.5, "y": 3.5, "deg": -90.0, "ref_offset": (0.0, -2.2)},
    "C2": {"x": 11.5, "y": 13.66, "deg": 0.0, "ref_offset": (1.0, -3.6)},
    "C1": {"x": 16.5, "y": 3.5, "deg": -90.0, "ref_offset": (0.0, -2.2)},
    "R2": {"x": 20.0, "y": 3.5, "deg": -90.0, "ref_offset": (0.0, -2.2)},
    "R3": {"x": 16.5, "y": 16.5, "deg": -90.0, "ref_offset": (-2.4, 5.08)},
    "R4": {"x": 21.0, "y": 16.5, "deg": -90.0, "ref_offset": (2.4, 5.08)},
    "CV1": {"x": 25.0, "y": 3.5, "deg": -90.0, "ref_offset": (0.0, -2.2)},
    "Q1": {"x": 25.0, "y": 12.5, "deg": -90.0, "ref_offset": (0.0, 7.2)},
    "C3": {"x": 29.8, "y": 12.5, "deg": -90.0, "ref_offset": (0.0, -2.2)},
    "L1": {"x": 34.0, "y": 3.5, "deg": -90.0, "ref_offset": (0.0, -2.2)},
    "AE1": {"x": 34.0, "y": 16.0, "deg": 0.0, "ref_offset": (0.0, -2.5)},
    "C4": {"x": 38.5, "y": 11.0, "deg": -90.0, "ref_offset": (0.0, -2.2)},
    "BT1": {"x": 42.5, "y": 12.0, "deg": 0.0, "ref_offset": (0.0, -2.5)},
}

TRACK_CHAINS = [
    ("Net-(J1-Pin_1)", 0.8, [(3.5, 5.5), (5.5, 3.5), (7.5, 3.5)]),
    ("Net-(C2-Pad1)", 0.8, [(3.5, 14.5), (6.66, 14.5), (7.5, 13.66), (11.5, 13.66)]),
    ("Net-(Q1-B)", 0.8, [
        (16.5, 8.5), (16.5, 10.66), (13.5, 13.66),
        (13.5, 13.66), (16.66, 13.66), (20.0, 13.66),
    ]),
    ("Net-(Q1-B)", 0.8, [
        (16.66, 13.66), (19.5, 16.5), (16.5, 16.5),
        (16.5, 16.5), (18.8, 18.8), (23.78, 18.8), (25.0, 17.58),
    ]),
    ("Net-(Q1-E)", 0.8, [
        (21.0, 16.5), (22.46, 15.04), (25.0, 15.04),
        (27.34, 15.04), (29.8, 17.5),
    ]),
    ("Net-(AE1-A)", 1.0, [
        (25.0, 8.5), (25.0, 12.5),
        (25.0, 12.5), (26.2, 13.7), (28.6, 13.7), (29.8, 12.5),
        (29.8, 12.5), (31.18, 11.12), (34.0, 11.12),
        (34.0, 11.12), (35.2, 12.32), (35.2, 14.8), (34.0, 16.0),
    ]),
    ("VCC", 1.2, [
        (20.0, 3.5), (25.0, 3.5), (34.0, 3.5),
        (36.7, 3.5), (38.5, 5.3), (38.5, 11.0),
        (38.5, 11.0), (39.5, 12.0), (42.5, 12.0),
    ]),
    ("GND", 1.0, [(38.5, 16.0), (41.04, 16.0), (42.5, 14.54)]),
    ("GND", 1.0, [(16.5, 26.66), (21.0, 26.66)]),
]


def parse_schematic_netlist():
    with tempfile.TemporaryDirectory() as directory:
        xml_path = Path(directory) / "netlist.xml"
        subprocess.run(
            [str(KICAD_CLI), "sch", "export", "netlist", "--format", "kicadxml", "-o", str(xml_path), str(SCH_PATH)],
            check=True,
            capture_output=True,
            text=True,
        )
        root = ElementTree.parse(xml_path).getroot()
        components = {}
        for comp in root.find("components").findall("comp"):
            ref = comp.get("ref")
            components[ref] = {
                "value": comp.findtext("value", ""),
                "footprint": comp.findtext("footprint", ""),
                "tstamp": comp.findtext("tstamps", ""),
            }
        nets = {}
        for net in root.find("nets").findall("net"):
            name = net.get("name")
            code = int(net.get("code"))
            nodes = [(node.get("ref"), node.get("pin")) for node in net.findall("node")]
            nets[name] = {"code": code, "nodes": nodes}
        return components, nets


def load_footprint(fp_id):
    lib, name = fp_id.split(":", 1)
    lib_path = FOOTPRINTS_DIR / f"{lib}.pretty"
    fp = pcbnew.FootprintLoad(str(lib_path), name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def add_edge_outline(board):
    corners = [(0.0, 0.0), (BOARD_W, 0.0), (BOARD_W, BOARD_H), (0.0, BOARD_H)]
    for i in range(4):
        x1, y1 = corners[i]
        x2, y2 = corners[(i + 1) % 4]
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetStart(pt(x1, y1))
        seg.SetEnd(pt(x2, y2))
        seg.SetWidth(pcbnew.FromMM(0.15))
        board.Add(seg)


def add_silkscreen_labels(board):
    title = pcbnew.PCB_TEXT(board)
    title.SetText("TX FM PN2222A/BF494")
    title.SetLayer(pcbnew.F_SilkS)
    title.SetPosition(pt(32.0, 24.5))
    title.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.0), pcbnew.FromMM(1.0)))
    title.SetTextThickness(pcbnew.FromMM(0.15))
    board.Add(title)

    copper_mark = pcbnew.PCB_TEXT(board)
    copper_mark.SetText("TELC02A")
    copper_mark.SetLayer(pcbnew.B_Cu)
    copper_mark.SetPosition(pt(33.0, 26.5))
    copper_mark.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.5), pcbnew.FromMM(1.5)))
    copper_mark.SetTextThickness(pcbnew.FromMM(0.35))
    copper_mark.SetMirrored(True)
    copper_mark.SetIsKnockout(True)
    board.Add(copper_mark)


def generate_pcb():
    components, nets = parse_schematic_netlist()
    board = pcbnew.NewBoard(str(PCB_PATH))
    board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(1.6))

    net_items = {}
    for net_name, spec in nets.items():
        net_item = pcbnew.NETINFO_ITEM(board, net_name, spec["code"])
        board.Add(net_item)
        net_items[net_name] = net_item

    pin_to_net = {}
    for net_name, spec in nets.items():
        for ref, pin in spec["nodes"]:
            pin_to_net[(ref, pin)] = net_items[net_name]

    add_edge_outline(board)

    for ref, comp in components.items():
        layout = COMPONENT_LAYOUT[ref]
        fp = load_footprint(comp["footprint"])
        fp.SetReference(ref)
        fp.SetValue(comp["value"])
        fp.SetPath(pcbnew.KIID_PATH(f"/{comp['tstamp']}"))
        fp.SetSheetfile("transmissor_te1.kicad_sch")
        fp.SetSheetname("")
        fp.SetPosition(pt(layout["x"], layout["y"]))
        fp.SetOrientationDegrees(layout["deg"])

        rx, ry = layout["ref_offset"]
        fp.Reference().SetPosition(pt(layout["x"] + rx, layout["y"] + ry))
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.0), pcbnew.FromMM(1.0)))
        fp.Reference().SetTextThickness(pcbnew.FromMM(0.15))
        fp.Value().SetVisible(False)

        for pad in fp.Pads():
            logical_pin = pad.GetNumber()
            if (ref, logical_pin) in pin_to_net:
                pad.SetNet(pin_to_net[(ref, logical_pin)])

        board.Add(fp)

    for net_name, width_mm, points in TRACK_CHAINS:
        net_item = net_items[net_name]
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if (x1, y1) == (x2, y2):
                continue
            track = pcbnew.PCB_TRACK(board)
            track.SetLayer(pcbnew.B_Cu)
            track.SetStart(pt(x1, y1))
            track.SetEnd(pt(x2, y2))
            track.SetWidth(pcbnew.FromMM(width_mm))
            track.SetNet(net_item)
            board.Add(track)

    gnd_zone = pcbnew.ZONE(board)
    gnd_zone.SetNet(net_items["GND"])
    gnd_zone.SetLayer(pcbnew.B_Cu)
    gnd_zone.SetLocalClearance(pcbnew.FromMM(0.5))
    gnd_zone.SetMinThickness(pcbnew.FromMM(0.3))
    gnd_zone.SetThermalReliefGap(pcbnew.FromMM(0.4))
    gnd_zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.5))
    gnd_zone.Outline().NewOutline()
    zone_corners = [
        (0.4, 1.4), (1.4, 0.4),
        (BOARD_W - 1.4, 0.4), (BOARD_W - 0.4, 1.4),
        (BOARD_W - 0.4, BOARD_H - 1.4), (BOARD_W - 1.4, BOARD_H - 0.4),
        (1.4, BOARD_H - 0.4), (0.4, BOARD_H - 1.4),
    ]
    for zx, zy in zone_corners:
        gnd_zone.AppendCorner(pt(zx, zy), -1)
    board.Add(gnd_zone)

    add_silkscreen_labels(board)

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())

    pcbnew.SaveBoard(str(PCB_PATH), board)
    export_production_pdfs()


def tile_pdf_content_stream(raw_stream):
    coords = [
        (float(x), float(y))
        for x, y in re.findall(r"([\d.]+)\s+([\d.]+)\s+[ml]", raw_stream)
    ]
    min_x = min(x for x, _ in coords)
    min_y = min(y for _, y in coords)
    mm_to_pt = 72.0 / 25.4
    orig_x_pt = min_x * 0.0072
    orig_y_pt = min_y * 0.0072
    page_w_mm = 297.0
    page_h_mm = 210.0
    grid_w_mm = TILE_COLS * BOARD_W + (TILE_COLS - 1) * TILE_GAP_MM
    grid_h_mm = TILE_ROWS * BOARD_H + (TILE_ROWS - 1) * TILE_GAP_MM
    start_x_mm = (page_w_mm - grid_w_mm) / 2.0
    start_y_mm = (page_h_mm - grid_h_mm) / 2.0

    blocks = []
    for row in range(TILE_ROWS):
        for col in range(TILE_COLS):
            target_x_mm = start_x_mm + col * (BOARD_W + TILE_GAP_MM)
            target_y_mm = start_y_mm + (TILE_ROWS - 1 - row) * (BOARD_H + TILE_GAP_MM)
            dx_pt = target_x_mm * mm_to_pt - orig_x_pt
            dy_pt = target_y_mm * mm_to_pt - orig_y_pt
            blocks.append(f"q 1 0 0 1 {dx_pt:.4f} {dy_pt:.4f} cm\n{raw_stream}\nQ")
    return "\n".join(blocks)


def write_tiled_single_page_pdf(source_pdf_path, dest_pdf_path):
    data = source_pdf_path.read_bytes()
    stream_match = re.search(
        rb"5\s+0\s+obj\s*<<.*?>>\s*stream\r?\n(.*?)\r?\nendstream",
        data,
        re.S,
    )
    raw_stream = zlib.decompress(stream_match.group(1)).decode("latin1")
    tiled_stream = tile_pdf_content_stream(raw_stream)
    compressed = zlib.compress(tiled_stream.encode("latin1"), 9)

    objects = [
        (1, b"<< /Type /Catalog /Pages 2 0 R /Version /1.5 >>"),
        (2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        (
            3,
            b"<< /Type /Page /Parent 2 0 R "
            b"/Resources << /ProcSet [/PDF /Text /ImageC /ImageB] /Font << /KicadFont 5 0 R >> >> "
            b"/MediaBox [0 0 841.896 595.296] /Contents 4 0 R >>",
        ),
        (
            4,
            f"<< /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode("latin1")
            + compressed
            + b"\nendstream",
        ),
        (
            5,
            b"<< /BaseFont /Helvetica /Type /Font /Subtype /Type1 /Encoding /WinAnsiEncoding >>",
        ),
    ]

    output = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for obj_num, body in objects:
        offsets[obj_num] = len(output)
        output.extend(f"{obj_num} 0 obj\n".encode("latin1"))
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin1"))
    output.extend(b"0000000000 65535 f \n")
    for obj_num in range(1, len(objects) + 1):
        output.extend(f"{offsets[obj_num]:010d} 00000 n \n".encode("latin1"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin1")
    )
    dest_pdf_path.write_bytes(bytes(output))


def export_production_pdfs():
    with tempfile.TemporaryDirectory() as directory:
        single_toner = Path(directory) / "single_toner.pdf"
        single_mirror = Path(directory) / "single_mirror.pdf"
        subprocess.run(
            [
                str(KICAD_CLI), "pcb", "export", "pdf",
                "--layers", "B.Cu,Edge.Cuts",
                "--black-and-white",
                "--exclude-refdes",
                "--exclude-value",
                "--drill-shape-opt", "2",
                "-o", str(single_toner),
                str(PCB_PATH),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                str(KICAD_CLI), "pcb", "export", "pdf",
                "--layers", "B.Cu,Edge.Cuts",
                "--mirror",
                "--black-and-white",
                "--exclude-refdes",
                "--exclude-value",
                "--drill-shape-opt", "2",
                "-o", str(single_mirror),
                str(PCB_PATH),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        write_tiled_single_page_pdf(single_toner, TONER_PDF_PATH)
        write_tiled_single_page_pdf(single_mirror, TONER_MIRROR_PDF_PATH)

    subprocess.run(
        [
            str(KICAD_CLI), "pcb", "export", "pdf",
            "--layers", "F.SilkS,F.Fab,Edge.Cuts",
            "--black-and-white",
            "--drill-shape-opt", "2",
            "-o", str(MONTAGEM_PDF_PATH),
            str(PCB_PATH),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


if __name__ == "__main__":
    generate_pcb()
