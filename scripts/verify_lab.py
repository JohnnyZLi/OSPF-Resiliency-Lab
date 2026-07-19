#!/usr/bin/env python3
"""Verify OSPF state, fail one core router, and record reconvergence evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = json.loads((ROOT / "inventory.json").read_text(encoding="utf-8"))
LAB_NAME = INVENTORY["lab_name"]
SOURCE_NODE = "edge-west"
DESTINATION = INVENTORY["test_prefix"]
PRIMARY_NEXT_HOPS = {"10.0.12.2", "10.0.13.2"}
SURVIVING_NEXT_HOPS = {"10.0.13.2"}


class VerificationError(RuntimeError):
    pass


@dataclass
class VerificationReport:
    timestamp_utc: str
    lab: str
    source: str
    destination: str
    baseline_full_neighbors: dict[str, int]
    baseline_next_hops: list[str]
    failure_injected: str
    failed_path_next_hops: list[str]
    reconvergence_seconds: float
    reachability_during_failure: bool
    restored_next_hops: list[str]
    recovery_seconds: float
    result: str


def container_name(node: str) -> str:
    return f"clab-{LAB_NAME}-{node}"


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True)
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise VerificationError(f"{' '.join(command)}: {detail}")
    return result


def docker(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["docker", *arguments], check=check)


def vtysh(node: str, command: str) -> str:
    return docker("exec", container_name(node), "vtysh", "-c", command).stdout


def count_full_neighbors(output: str) -> int:
    return sum("Full/" in line for line in output.splitlines())


def parse_nexthops(output: str, prefix: str) -> set[str]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"FRR returned invalid route JSON: {exc}") from exc

    routes = payload.get(prefix, [])
    if isinstance(routes, dict):
        routes = [routes]
    next_hops: set[str] = set()
    for route in routes:
        if route.get("selected") is False:
            continue
        for next_hop in route.get("nexthops", []):
            if next_hop.get("active") is False:
                continue
            address = next_hop.get("ip")
            if address:
                next_hops.add(address)
    return next_hops


def current_nexthops() -> set[str]:
    return parse_nexthops(vtysh(SOURCE_NODE, f"show ip route {DESTINATION} json"), DESTINATION)


def current_neighbor_counts() -> dict[str, int]:
    return {
        node: count_full_neighbors(vtysh(node, "show ip ospf neighbor"))
        for node in INVENTORY["nodes"]
    }


def wait_for(
    description: str,
    probe: Callable[[], object],
    predicate: Callable[[object], bool],
    timeout: float = 45.0,
    interval: float = 0.5,
) -> tuple[object, float]:
    started = time.monotonic()
    last_value: object = None
    while time.monotonic() - started < timeout:
        try:
            last_value = probe()
            if predicate(last_value):
                return last_value, time.monotonic() - started
        except (VerificationError, json.JSONDecodeError):
            pass
        time.sleep(interval)
    raise VerificationError(f"Timed out waiting for {description}; last value: {last_value}")


def expected_neighbors(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return all(
        value.get(node) == details["expected_full_neighbors"]
        for node, details in INVENTORY["nodes"].items()
    )


def ping_destination() -> bool:
    result = docker(
        "exec",
        container_name(SOURCE_NODE),
        "ping",
        "-c",
        "3",
        "-W",
        "1",
        DESTINATION.split("/")[0],
        check=False,
    )
    return result.returncode == 0


def verify(report_path: Path | None = None, skip_failure: bool = False) -> VerificationReport | None:
    neighbor_value, _ = wait_for(
        "all OSPF adjacencies",
        current_neighbor_counts,
        expected_neighbors,
    )
    baseline_value, _ = wait_for(
        "two equal-cost paths",
        current_nexthops,
        lambda value: value == PRIMARY_NEXT_HOPS,
    )
    if not ping_destination():
        raise VerificationError("Baseline ping failed")

    print(f"PASS: all OSPF adjacencies are Full: {neighbor_value}")
    print(f"PASS: baseline ECMP next hops: {sorted(baseline_value)}")
    print(f"PASS: {SOURCE_NODE} can reach {DESTINATION}")

    if skip_failure:
        return None

    paused = False
    try:
        docker("pause", container_name("core-a"))
        paused = True
        failed_value, convergence = wait_for(
            "traffic to reconverge through core-b",
            current_nexthops,
            lambda value: value == SURVIVING_NEXT_HOPS,
        )
        reachable = ping_destination()
        if not reachable:
            raise VerificationError("Destination was unreachable after OSPF reconvergence")
        print(f"PASS: core-a failure removed its path in {convergence:.3f}s")
        print(f"PASS: surviving next hop: {sorted(failed_value)}")
    finally:
        if paused:
            docker("unpause", container_name("core-a"), check=False)

    restored_value, recovery = wait_for(
        "both equal-cost paths to return",
        current_nexthops,
        lambda value: value == PRIMARY_NEXT_HOPS,
    )
    wait_for("all OSPF adjacencies to recover", current_neighbor_counts, expected_neighbors)
    print(f"PASS: ECMP restored in {recovery:.3f}s: {sorted(restored_value)}")

    report = VerificationReport(
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        lab=LAB_NAME,
        source=SOURCE_NODE,
        destination=DESTINATION,
        baseline_full_neighbors=dict(neighbor_value),
        baseline_next_hops=sorted(baseline_value),
        failure_injected=f"docker pause {container_name('core-a')}",
        failed_path_next_hops=sorted(failed_value),
        reconvergence_seconds=round(convergence, 3),
        reachability_during_failure=reachable,
        restored_next_hops=sorted(restored_value),
        recovery_seconds=round(recovery, 3),
        result="pass",
    )

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8")
        print(f"Evidence written to {report_path}")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Write JSON evidence to this path")
    parser.add_argument("--skip-failure", action="store_true", help="Check baseline state without pausing core-a")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        verify(args.report, args.skip_failure)
    except (VerificationError, FileNotFoundError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
