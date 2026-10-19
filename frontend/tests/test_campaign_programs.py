"""Read-only source/provenance checks for the campaign's original-code index.

These tests verify citations against retained bytes. They do not execute AGC
programs, complete a mission stage, or establish an API capability.
"""

from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import unittest
from urllib.parse import quote, urlparse


ROOT = Path(__file__).resolve().parents[2]
REVISION = "f577e3fd917866c59334e6cdd32504f09df76f60"
CMC_ARCHIVE = "docs/earth-orbit-evidence/corresponding-source.tar.gz"
LGC_LISTING = "docs/phase9-evidence/setup/prepared-assembly-1/Luminary099/MAIN.agc.lst.gz"
LGC_MANIFEST = "docs/phase9-evidence/setup/setups/20261017T181903Z-486ff63e/source-archive-hashes.json"
CMC_ARCHIVE_SHA = "8828f9a0f7e529b7072690a447d63385e67ab12e768a1cd4b199a642a79eac3d"
LGC_LISTING_SHA = "2ddf3731093b06a93dc3428704bae338f0e0790b9214e8238406f7febb0724e0"


def checked_path(relative):
    """Source metadata cannot escape the project or acquire a network resource."""
    if not isinstance(relative, str):
        raise ValueError("Source path must be text")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ValueError("Unsafe source path")
    result = ROOT.joinpath(*path.parts)
    if not result.is_file():
        raise ValueError("Missing retained source")
    return result


def read_original_sources():
    sources = {}
    with tarfile.open(checked_path(CMC_ARCHIVE)) as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.startswith("Comanche055/") and member.name.endswith(".agc"):
                raw = archive.extractfile(member).read()
                sources[member.name] = {
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "lines": list(enumerate(raw.decode().splitlines(), 1)),
                }
    manifest = json.loads(checked_path(LGC_MANIFEST).read_text())
    current = None
    for row in gzip.decompress(checked_path(LGC_LISTING).read_bytes()).decode().splitlines():
        match = re.match(r"\d+,\d+: \$(\S+\.agc)", row)
        if match:
            current = "Luminary099/" + match[1]
            sources[current] = {"sha256": manifest[current], "lines": []}
            continue
        if row.startswith("(End of include-file"):
            current = None
            continue
        if current and re.match(r"\d{6},\d{6}: ", row):
            sources[current]["lines"].append((int(row[7:13]), row[46:].rstrip()))
    return sources


def validate_reference(ref, sources):
    required = {"softwareId", "program", "label", "file", "symbol", "line", "sourceSha256",
                "listingUrl", "pinnedSourceUrl", "localSource", "excerpt", "excerptLineNumbers", "scope"}
    if not isinstance(ref, dict) or not required.issubset(ref):
        raise ValueError("Missing original-program metadata")
    folder = {"comanche055": "Comanche055", "luminary099": "Luminary099"}.get(ref["softwareId"])
    if folder is None or not ref["file"].startswith(folder + "/"):
        raise ValueError("Wrong computer/source family")
    filename = ref["file"].split("/", 1)[1]
    if "/" in filename or not filename.endswith(".agc") or ref["file"] not in sources:
        raise ValueError("Unknown original source member")
    local = ref["localSource"]
    expected_path = CMC_ARCHIVE if folder == "Comanche055" else LGC_LISTING
    expected_kind = "archive-member" if folder == "Comanche055" else "assembly-listing"
    if local.get("path") != expected_path or local.get("kind") != expected_kind or local.get("member") != ref["file"]:
        raise ValueError("Incorrect local source locator")
    checked_path(local["path"])
    original = sources[ref["file"]]
    if ref["sourceSha256"] != original["sha256"]:
        raise ValueError("Original source hash mismatch")
    if type(ref["line"]) is not int or ref["line"] < 1:
        raise ValueError("Invalid original source line")
    symbol = ref["symbol"]
    if not isinstance(symbol, str) or not symbol or "\n" in symbol:
        raise ValueError("Invalid source symbol")
    lines = original["lines"]
    matches = [i for i, (number, text) in enumerate(lines)
               if number == ref["line"] and re.match(re.escape(symbol) + r"\s", text)]
    if len(matches) != 1:
        raise ValueError("Symbol does not occur at the cited source line")
    excerpt = ref["excerpt"].split("\n")
    if not 1 <= len(excerpt) <= 10:
        raise ValueError("Invalid excerpt length")
    expected = lines[matches[0]:matches[0] + len(excerpt)]
    if ref["excerptLineNumbers"] != [n for n, _ in expected] or excerpt != [text for _, text in expected]:
        raise ValueError("Excerpt differs from the retained source")
    escaped = quote(filename, safe=",-_")
    expected_listing = f"https://www.ibiblio.org/apollo/listings/{folder}/{escaped}.html"
    expected_pinned = f"https://github.com/virtualagc/virtualagc/blob/{REVISION}/{folder}/{escaped}"
    if ref["listingUrl"] != expected_listing or ref["pinnedSourceUrl"] != expected_pinned:
        raise ValueError("Source link is not the identified original listing")
    for key in ("listingUrl", "pinnedSourceUrl"):
        if urlparse(ref[key]).scheme != "https":
            raise ValueError("Source link must use HTTPS")


class CampaignOriginalProgramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "frontend/dist/data/campaign-programs.json").read_text())
        cls.catalog = json.loads((ROOT / "frontend/dist/data/apollo-campaign.json").read_text())
        cls.sources = read_original_sources()
        cls.refs = [p for stage in cls.data["stages"] for p in stage["originalPrograms"]]

    def test_all_sixteen_stages_keep_catalog_order_and_capability_requirements(self):
        self.assertEqual(self.data["schemaVersion"], 1)
        self.assertEqual(len(self.data["stages"]), 16)
        self.assertEqual([s["stageId"] for s in self.data["stages"]], [s["id"] for s in self.catalog["stages"]])
        for stage, chapter in zip(self.data["stages"], self.catalog["stages"]):
            self.assertEqual(stage["title"], chapter["title"])
            self.assertEqual(stage["requiredCapability"], chapter["requiredCapabilities"][0])
            self.assertEqual(stage["historicalSourceIds"], chapter["sourceIds"])
            self.assertTrue(stage["station"] and stage["controlAuthority"] and stage["nextIntegration"])
            self.assertTrue(stage["missingSystems"])
            self.assertIs(stage["completeFlightAvailable"], False)

    def test_retained_container_hashes_and_software_provenance_are_identified(self):
        software = {entry["id"]: entry for entry in self.data["software"]}
        self.assertEqual(set(software), {"comanche055", "luminary099"})
        self.assertEqual(hashlib.sha256(checked_path(CMC_ARCHIVE).read_bytes()).hexdigest(), CMC_ARCHIVE_SHA)
        self.assertEqual(software["comanche055"]["archiveSha256"], CMC_ARCHIVE_SHA)
        self.assertEqual(hashlib.sha256(checked_path(LGC_LISTING).read_bytes()).hexdigest(), LGC_LISTING_SHA)
        self.assertEqual(software["luminary099"]["assemblyListingSha256"], LGC_LISTING_SHA)
        self.assertEqual(software["luminary099"]["sourceManifestPath"], LGC_MANIFEST)
        self.assertIn("099/0", software["luminary099"]["version"])
        self.assertIn("099/1", software["luminary099"]["provenanceNote"])
        for entry in software.values():
            self.assertEqual(entry["upstreamRevision"], REVISION)
            checked_path(entry["binaryPath"])

    def test_all_original_excerpts_symbols_lines_and_hashes_match_local_evidence(self):
        unique = {(r["file"], r["symbol"]): r for r in self.refs}
        self.assertEqual(len(unique), 23)
        self.assertEqual(len({r["file"] for r in self.refs}), 15)
        for ref in unique.values():
            with self.subTest(file=ref["file"], symbol=ref["symbol"]):
                validate_reference(ref, self.sources)

    def test_repeated_program_references_keep_the_same_citation(self):
        originals = {}
        for ref in self.refs:
            key = ref["file"], ref["symbol"]
            if key in originals:
                self.assertEqual(ref, originals[key])
            originals[key] = ref

    def test_source_index_cannot_claim_flight_or_replace_the_correct_computer(self):
        self.assertEqual(self.data["classification"], "SOURCE_INDEX_ONLY")
        self.assertIn("does not execute", self.data["executionDisclaimer"])
        self.assertIn("proposed", self.data["capabilityNote"])
        stages = {s["stageId"]: s for s in self.data["stages"]}
        self.assertEqual(stages["earth-parking"]["availability"], "original-task")
        self.assertEqual(stages["tli"]["availability"], "source-only")
        self.assertIn("01204", " ".join(stages["tli"]["missingSystems"]))
        self.assertIn("LVDC", " ".join(stages["tli"]["missingSystems"]))
        self.assertFalse(any(r["program"] == "P15" for r in self.refs))
        self.assertTrue(all(r["softwareId"] == "comanche055" for r in stages["entry-splashdown"]["originalPrograms"]))
        self.assertTrue(all(r["softwareId"] == "luminary099" for r in stages["powered-descent"]["originalPrograms"]))
        self.assertIn("hardware", stages["rendezvous-docking"]["station"])
        # No endpoint is inferred from static source metadata.
        forbidden = {"endpoint", "commandEndpoint", "executeUrl", "apiUrl", "telemetry"}
        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(self.data)

    def test_modified_hash_excerpt_and_source_line_are_rejected(self):
        for mutate, message in (
            (lambda r: r.update(sourceSha256="0" * 64), "hash mismatch"),
            (lambda r: r.update(line=r["line"] + 1), "cited source line"),
            (lambda r: r.update(excerpt=r["excerpt"].replace("TC", "CA", 1)), "differs from"),
        ):
            ref = deepcopy(self.refs[0])
            mutate(ref)
            with self.assertRaisesRegex(ValueError, message):
                validate_reference(ref, self.sources)

    def test_unsafe_paths_and_unrelated_source_links_are_rejected_without_fetching(self):
        for path in ("../private-source", "/etc/passwd", "https://example.com/source"):
            with self.assertRaises(ValueError):
                checked_path(path)
        ref = deepcopy(self.refs[0])
        ref["listingUrl"] = "javascript:alert(1)"
        with self.assertRaisesRegex(ValueError, "Source link"):
            validate_reference(ref, self.sources)
        ref = deepcopy(self.refs[0])
        ref["localSource"]["member"] = "../Comanche055/P51-P53.agc"
        with self.assertRaisesRegex(ValueError, "local source locator"):
            validate_reference(ref, self.sources)


if __name__ == "__main__":
    unittest.main()
