# Verification evidence

`scripts/verify_lab.py` writes a JSON report here after it has:

1. confirmed every expected OSPF adjacency is Full;
2. confirmed two equal-cost paths from `edge-west` to `10.255.0.4/32`;
3. paused `core-a` to simulate a silent node failure;
4. measured the time until only the `core-b` path remains;
5. verified reachability during the failure; and
6. restored `core-a` and confirmed both paths return.

Local reports are ignored because measurements depend on the host. The GitHub Actions workflow uploads its report as the `ospf-verification-evidence` artifact on each successful integration run.
