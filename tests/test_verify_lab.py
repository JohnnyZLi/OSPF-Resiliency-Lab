import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_lab import count_full_neighbors, parse_nexthops, container_name  # noqa: E402


class VerifierParsingTests(unittest.TestCase):
    def test_counts_only_full_adjacencies(self) -> None:
        output = """Neighbor ID Pri State Dead Time Address Interface
10.255.0.2 1 Full/- 2.8s 10.0.12.2 eth1:10.0.12.1
10.255.0.3 1 Full/- 2.6s 10.0.13.2 eth2:10.0.13.1
10.255.0.9 1 Init/- 2.1s 10.0.19.2 eth9:10.0.19.1
"""
        self.assertEqual(count_full_neighbors(output), 2)

    def test_extracts_active_selected_nexthops(self) -> None:
        prefix = "10.255.0.4/32"
        payload = {
            prefix: [
                {
                    "selected": True,
                    "nexthops": [
                        {"ip": "10.0.12.2", "active": True},
                        {"ip": "10.0.13.2", "active": True},
                    ],
                },
                {
                    "selected": False,
                    "nexthops": [{"ip": "192.0.2.1", "active": True}],
                },
            ]
        }
        self.assertEqual(parse_nexthops(json.dumps(payload), prefix), {"10.0.12.2", "10.0.13.2"})

    def test_ignores_inactive_nexthops(self) -> None:
        prefix = "10.255.0.4/32"
        payload = {prefix: {"selected": True, "nexthops": [{"ip": "10.0.12.2", "active": False}]}}
        self.assertEqual(parse_nexthops(json.dumps(payload), prefix), set())

    def test_uses_containerlab_naming_convention(self) -> None:
        self.assertEqual(container_name("core-a"), "clab-ospf-resilience-core-a")


if __name__ == "__main__":
    unittest.main()
