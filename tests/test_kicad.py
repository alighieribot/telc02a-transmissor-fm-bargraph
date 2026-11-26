import json
import math
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ElementTree
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import netlist_tools as nt
from generate_kicad import TRANSMITTER_PLACEMENT, VU_PLACEMENT

KICAD_CLI = Path(r"C:\Users\alighieribot\AppData\Local\Programs\KiCad\9.0\bin\kicad-cli.exe")

CIRCUITS = {
    "transmissor_te1": (ROOT / "kicad" / "transmissor" / "transmissor_te1.kicad_sch",
                        ROOT / "netlists" / "transmissor_te1.json", TRANSMITTER_PLACEMENT),
    "vu_meter_lm3915": (ROOT / "kicad" / "vu_meter" / "vu_meter_lm3915.kicad_sch",
                        ROOT / "netlists" / "vu_meter_lm3915.json", VU_PLACEMENT),
}


def run_cli(*arguments):
    return subprocess.run([str(KICAD_CLI), *arguments], capture_output=True, text=True, check=True)


def exported_partition(schematic):
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "netlist.xml"
        completed = run_cli("sch", "export", "netlist", "--format", "kicadxml", "-o", str(output), str(schematic))
        nets = ElementTree.parse(output).getroot().find("nets")
        partition = {
            frozenset(f"{node.get('ref')}.{node.get('pin')}" for node in net.findall("node"))
            for net in nets.findall("net")
        }
        return partition, completed.stderr


def declared_partition(netlist, placement):
    return {
        frozenset(f"{pin.split('.')[0]}.{placement[pin.split('.')[0]]['pins'][pin.split('.', 1)[1]]}" for pin in pins)
        for pins in netlist["nets"].values()
    }


@unittest.skipUnless(KICAD_CLI.exists(), "kicad-cli indisponivel")
class KicadSchematics(unittest.TestCase):
    def test_exported_netlist_matches_declared_netlist(self):
        for name, (schematic, netlist_path, placement) in CIRCUITS.items():
            with self.subTest(circuit=name):
                exported, _ = exported_partition(schematic)
                self.assertEqual(exported, declared_partition(nt.load_netlist(netlist_path), placement))

    def test_no_annotation_errors(self):
        for name, (schematic, _, _) in CIRCUITS.items():
            with self.subTest(circuit=name):
                _, stderr = exported_partition(schematic)
                self.assertNotIn("annotation errors", stderr)

    def test_electrical_rules_check_has_no_violations(self):
        for name, (schematic, _, _) in CIRCUITS.items():
            with self.subTest(circuit=name):
                with tempfile.TemporaryDirectory() as directory:
                    report = Path(directory) / "erc.json"
                    run_cli("sch", "erc", "--format", "json", "--severity-all", "-o", str(report), str(schematic))
                    data = json.loads(report.read_text(encoding="utf-8"))
                    violations = [v for sheet in data["sheets"] for v in sheet["violations"]]
                    self.assertEqual(violations, [])

    def test_transmitter_pcb_design_rules_and_schematic_parity(self):
        pcb_path = ROOT / "kicad" / "transmissor" / "transmissor_te1.kicad_pcb"
        self.assertTrue(pcb_path.exists())
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "drc.json"
            run_cli(
                "pcb", "drc", "--format", "json", "--schematic-parity",
                "--severity-all", "-o", str(report), str(pcb_path),
            )
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["violations"], [])
            self.assertEqual(data["unconnected_items"], [])
            self.assertEqual(data["schematic_parity"], [])

    def test_transmitter_pcb_tracks_are_trapezoidal_without_right_angles(self):
        pcb_text = (ROOT / "kicad" / "transmissor" / "transmissor_te1.kicad_pcb").read_text(encoding="utf-8")
        segments = re.findall(
            r"\(segment\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)",
            pcb_text,
        )
        self.assertGreater(len(segments), 10)
        vectors_at_vertex = {}
        for x1_s, y1_s, x2_s, y2_s in segments:
            x1, y1, x2, y2 = float(x1_s), float(y1_s), float(x2_s), float(y2_s)
            dx, dy = round(x2 - x1, 4), round(y2 - y1, 4)
            self.assertTrue(
                abs(dx) < 1e-3 or abs(dy) < 1e-3 or abs(abs(dx) - abs(dy)) < 1e-2,
                f"Segment ({x1}, {y1}) -> ({x2}, {y2}) is neither orthogonal nor 45-degree mitered",
            )
            p1 = (round(x1, 3), round(y1, 3))
            p2 = (round(x2, 3), round(y2, 3))
            vectors_at_vertex.setdefault(p1, []).append((x2 - x1, y2 - y1))
            vectors_at_vertex.setdefault(p2, []).append((x1 - x2, y1 - y2))
        for vertex, vecs in vectors_at_vertex.items():
            for i in range(len(vecs)):
                for j in range(i + 1, len(vecs)):
                    vx1, vy1 = vecs[i]
                    vx2, vy2 = vecs[j]
                    norm = math.hypot(vx1, vy1) * math.hypot(vx2, vy2)
                    if norm > 0:
                        cos_angle = (vx1 * vx2 + vy1 * vy2) / norm
                        self.assertGreater(
                            abs(cos_angle), 0.1,
                            f"90-degree right angle detected at vertex {vertex}",
                        )

    def test_toner_transfer_pdfs_contain_16_replicated_1to1_copies(self):
        for filename in ("transmissor_te1_toner_transfer.pdf", "transmissor_te1_toner_transfer_mirror.pdf"):
            with self.subTest(pdf=filename):
                pdf_path = ROOT / "kicad" / "transmissor" / filename
                self.assertTrue(pdf_path.exists())
                raw_bytes = pdf_path.read_bytes()
                stream_match = re.search(
                    rb"4\s+0\s+obj\s*<<.*?>>\s*stream\r?\n(.*?)\r?\nendstream",
                    raw_bytes,
                    re.S,
                )
                self.assertIsNotNone(stream_match)
                content = zlib.decompress(stream_match.group(1)).decode("latin1")
                tiles = re.findall(r"q\s+1\s+0\s+0\s+1\s+([-\d.]+)\s+([-\d.]+)\s+cm\s+(.*?)\s+Q", content, re.S)
                self.assertEqual(len(tiles), 16)
                first_body = tiles[0][2]
                coords = [(float(x), float(y)) for x, y in re.findall(r"([\d.]+)\s+([\d.]+)\s+[ml]", first_body)]
                width_mm = (max(x for x, _ in coords) - min(x for x, _ in coords)) * 0.0072 * 25.4 / 72.0
                height_mm = (max(y for _, y in coords) - min(y for _, y in coords)) * 0.0072 * 25.4 / 72.0
                self.assertAlmostEqual(width_mm, 46.0, places=2)
                self.assertAlmostEqual(height_mm, 30.0, places=2)
                xs_pt = sorted({round(float(dx), 2) for dx, _, _ in tiles})
                ys_pt = sorted({round(float(dy), 2) for _, dy, _ in tiles})
                self.assertEqual(len(xs_pt), 4)
                self.assertEqual(len(ys_pt), 4)
                for a, b in zip(xs_pt, xs_pt[1:]):
                    self.assertAlmostEqual((b - a) * 25.4 / 72.0, 58.0, places=1)
                for a, b in zip(ys_pt, ys_pt[1:]):
                    self.assertAlmostEqual((b - a) * 25.4 / 72.0, 42.0, places=1)


if __name__ == "__main__":
    unittest.main()
