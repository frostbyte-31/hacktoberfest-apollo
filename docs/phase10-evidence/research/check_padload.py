#!/usr/bin/env python3
"""Independent validation of scan-transcribed mission-tape fixed-point data.

This is diagnostic arithmetic only. It never loads or executes an AGC.
"""
import json
from pathlib import Path


def decode(words, scale):
    raw = [int(word, 8) for word in words]
    if any(not 0 <= word <= 0o77777 for word in raw):
        raise ValueError("Not a 15-bit AGC word")
    if len(raw) == 1:
        negative = bool(raw[0] & 0o40000)
        magnitude = raw[0] ^ (0o77777 if negative else 0)
        return (-1 if negative else 1) * magnitude * 2.0 ** (scale - 14)
    if len(raw) != 2:
        raise ValueError("Expected SP or DP")
    if bool(raw[0] & 0o40000) != bool(raw[1] & 0o40000):
        raise ValueError("Noncanonical DP sign agreement")
    negative = bool(raw[0] & 0o40000)
    high, low = [word ^ (0o77777 if negative else 0) for word in raw]
    magnitude = high * 2**14 + low
    return (-1 if negative else 1) * magnitude * 2.0 ** (scale - 28)


def validate():
    data = json.loads(Path(__file__).with_name("padload-transcription.json").read_text())
    rows = []
    for item in data["mission_tape"]:
        count = 1 if len(item["words"]) == 1 else 2
        expected = item["printed_value"]
        expected = expected if isinstance(expected, list) else [expected]
        for index, printed in enumerate(expected):
            words = item["words"][count * index:count * (index + 1)]
            value = decode(words, item["sf"])
            quantum = 2.0 ** (item["sf"] - 14 * count)
            # Source decimal precision is coarser for several long constants.
            tolerance = max(0.5 * quantum, abs(printed) * 5e-9)
            error = abs(value - printed)
            # The canonical representable value below 1 is specified for GAINBRAK.
            if item["symbol"] == "GAINBRAK":
                tolerance = quantum
            if error > tolerance:
                raise AssertionError((item["symbol"], words, value, printed, tolerance))
            rows.append({"symbol": item["symbol"], "component": index,
                         "words": words, "decoded_value": value,
                         "printed_value": printed, "units": item["units"],
                         "quantum": quantum, "absolute_error": error,
                         "tolerance": tolerance, "within_tolerance": True})
    return {"classification": "INDEPENDENT VALIDATION; no AGC execution",
            "source": data["source"], "checked_components": len(rows), "values": rows}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
