# Design notes

## Objective

Demonstrate OSPF path selection and reconvergence in a topology where both edge routers have independent paths through two core routers. The test should prove the forwarding state before, during, and after a core failure.

## Topology

The normal path from `edge-west` to `edge-east` has equal OSPF cost through `core-a` and `core-b`. A core interconnect provides additional control-plane reachability but has an explicit cost of 50, so it does not displace either two-hop edge-to-edge path during normal operation.

| Link | Subnet | Cost |
| --- | --- | --- |
| edge-west — core-a | `10.0.12.0/30` | 1 |
| edge-west — core-b | `10.0.13.0/30` | 1 |
| core-a — edge-east | `10.0.24.0/30` | 1 |
| core-b — edge-east | `10.0.34.0/30` | 1 |
| core-a — core-b | `10.0.23.0/30` | 50 |

Each router advertises a `/32` loopback in area 0. The loopback is passive; only point-to-point transit interfaces form adjacencies.

## Failure model

The verifier pauses the `core-a` container instead of administratively shutting an interface. From its neighbors' perspective, the link stays up but Hello packets stop. That exercises OSPF's dead timer and control-plane reconvergence rather than relying on immediate interface-down detection.

The lab uses one-second Hello intervals and three-second dead intervals on every transit link. These values are deliberately aggressive for a compact lab and must match on both ends of each adjacency. They are not presented as a universal production recommendation.

## Verification contract

The run passes only when all of the following are true:

- the expected number of Full neighbors exists on every router;
- `edge-west` installs both core next hops for `10.255.0.4/32`;
- pausing `core-a` removes `10.0.12.2` from the selected route;
- `edge-west` can still ping the destination loopback;
- unpausing `core-a` restores both equal-cost next hops; and
- all expected adjacencies return to Full.

## References

- [Containerlab topology definition](https://containerlab.dev/manual/topo-def-file/)
- [Containerlab FRR example](https://containerlab.dev/lab-examples/peering-lab/)
- [FRRouting OSPFv2 documentation](https://docs.frrouting.org/en/latest/ospfd.html)
- [FRRouting releases and container image naming](https://frrouting.org/release/)
