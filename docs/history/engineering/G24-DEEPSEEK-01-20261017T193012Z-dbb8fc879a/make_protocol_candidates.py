"""Create balanced candidate blocks and a fixed arm-order schedule."""
from __future__ import annotations

import json
import random

from audit import E, write


SPECS = [
    ("P01", "PILOT", "A", "read-only-lock", "DELETE", 30, "POSITIVE_TRANSFER"),
    ("P02", "PILOT", "D", "buggy", "WAL", 30, "NEGATIVE_TRANSFER"),
    ("F01", "FORMAL", "A", "read-only-lock", "DELETE", 30, "POSITIVE_TRANSFER"),
    ("F02", "FORMAL", "A", "read-only-lock", "DELETE", 30, "POSITIVE_TRANSFER"),
    ("F03", "FORMAL", "D", "buggy", "DELETE", 30, "NEGATIVE_TRANSFER"),
    ("F04", "FORMAL", "D", "buggy", "WAL", 30, "NEGATIVE_TRANSFER"),
    ("F05", "FORMAL", "D", "split-ledger", "DELETE", 30, "NEGATIVE_TRANSFER"),
    ("F06", "FORMAL", "D-V02", "buggy", "DELETE", 30, "UNKNOWN_OR_CONFLICT"),
    ("F07", "FORMAL", "D-V02", "local_lock", "WAL", 30, "UNKNOWN_OR_CONFLICT"),
    ("F08", "FORMAL", "D-V02", "blind_cleanup", "DELETE", 30, "UNKNOWN_OR_CONFLICT"),
]
ARMS = ("GRAPH", "RAW_MEMORY", "NO_MEMORY")
SEED = 20261018


def balanced_orders(rng: random.Random, count: int) -> list[list[str]]:
    cycles = [
        ["GRAPH", "RAW_MEMORY", "NO_MEMORY"],
        ["RAW_MEMORY", "NO_MEMORY", "GRAPH"],
        ["NO_MEMORY", "GRAPH", "RAW_MEMORY"],
    ]
    result = [cycles[index % 3] for index in range(count)]
    rng.shuffle(result)
    return result


def main() -> int:
    rng = random.Random(SEED)
    orders = balanced_orders(rng, len(SPECS))
    blocks = []
    for (block, stage, episode, fault, journal, busy_timeout, condition), order in zip(SPECS, orders):
        blocks.append({
            "block": block,
            "stage": stage,
            "episode": episode,
            "fault": fault,
            "journal": journal,
            "busy_timeout": busy_timeout,
            "condition": condition,
            "seed": rng.randrange(2**31),
            "arm_order": order,
        })
    write(E / "01_protocol/TASKS_DRAFT.json", blocks)
    position_counts = {
        arm: [sum(order[index] == arm for order in orders) for index in range(3)]
        for arm in ARMS
    }
    write(E / "01_protocol/ARM_ORDER_BALANCE.json", {
        "seed": SEED,
        "block_count": len(SPECS),
        "position_counts": position_counts,
        "balanced": all(max(counts) - min(counts) <= 1 for counts in position_counts.values()),
    })
    print(json.dumps(position_counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
