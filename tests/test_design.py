import ipaddress
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = json.loads((ROOT / "inventory.json").read_text(encoding="utf-8"))


class AddressPlanTests(unittest.TestCase):
    def test_link_endpoints_are_unique_and_inside_declared_subnets(self) -> None:
        addresses: set[ipaddress.IPv4Address] = set()
        endpoint_names: set[str] = set()

        for link in INVENTORY["links"]:
            network = ipaddress.ip_network(link["subnet"])
            self.assertEqual(len(link["endpoints"]), 2)
            for endpoint in link["endpoints"]:
                node, interface = endpoint.split(":")
                address = ipaddress.ip_interface(INVENTORY["nodes"][node]["interfaces"][interface])
                self.assertIn(address.ip, network)
                self.assertNotIn(address.ip, addresses)
                self.assertNotIn(endpoint, endpoint_names)
                addresses.add(address.ip)
                endpoint_names.add(endpoint)

    def test_router_ids_are_unique_host_addresses(self) -> None:
        router_ids = [details["router_id"] for details in INVENTORY["nodes"].values()]
        self.assertEqual(len(router_ids), len(set(router_ids)))
        for node, details in INVENTORY["nodes"].items():
            self.assertEqual(details["interfaces"]["lo"], f"{details['router_id']}/32", node)


class TopologyTests(unittest.TestCase):
    def test_topology_matches_inventory_links(self) -> None:
        topology = (ROOT / "topology.clab.yml").read_text(encoding="utf-8")
        actual = {
            frozenset(pair)
            for pair in re.findall(r'- endpoints: \["([^"]+)", "([^"]+)"\]', topology)
        }
        expected = {frozenset(link["endpoints"]) for link in INVENTORY["links"]}
        self.assertEqual(actual, expected)

    def test_topology_pins_current_frr_image(self) -> None:
        topology = (ROOT / "topology.clab.yml").read_text(encoding="utf-8")
        self.assertIn("image: quay.io/frrouting/frr:10.7.0", topology)
        self.assertIn("net.ipv4.ip_forward: 1", topology)


class FrrConfigTests(unittest.TestCase):
    def test_configurations_match_inventory(self) -> None:
        for node, details in INVENTORY["nodes"].items():
            config = (ROOT / "configs" / node / "frr.conf").read_text(encoding="utf-8")
            self.assertIn(f"hostname {node}", config)
            self.assertIn("router ospf", config)
            self.assertIn(f"ospf router-id {details['router_id']}", config)
            self.assertIn("passive-interface default", config)
            for interface, address in details["interfaces"].items():
                self.assertRegex(config, rf"interface {re.escape(interface)}\n(?: .+\n)* ip address {re.escape(address)}")
                if interface != "lo":
                    self.assertIn(f"no passive-interface {interface}", config)
                    self.assertRegex(config, rf"interface {re.escape(interface)}\n(?: .+\n)* ip ospf hello-interval 1\n ip ospf dead-interval 3")

    def test_core_interconnect_has_higher_cost_on_both_ends(self) -> None:
        for node in ("core-a", "core-b"):
            config = (ROOT / "configs" / node / "frr.conf").read_text(encoding="utf-8")
            eth3 = config.split("interface eth3", 1)[1].split("!", 1)[0]
            self.assertIn("ip ospf cost 50", eth3)

    def test_only_required_routing_daemon_is_enabled(self) -> None:
        daemons = (ROOT / "configs" / "daemons").read_text(encoding="utf-8")
        self.assertIn("ospfd=yes", daemons)
        for daemon in ("bgpd", "ospf6d", "isisd", "ripd", "bfdd"):
            self.assertIn(f"{daemon}=no", daemons)


if __name__ == "__main__":
    unittest.main()
