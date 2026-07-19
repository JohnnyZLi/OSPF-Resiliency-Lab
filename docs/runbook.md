# Lab runbook

## Prerequisites

- A Linux host with Docker
- Containerlab 0.77.0 or a compatible newer release
- Python 3.11 or newer
- Permission to run Docker commands

The spare desktop running a Debian- or RHEL-family Linux distribution is the simplest target. On a Mac, run the lab inside a Linux virtual machine because Containerlab creates Linux network namespaces and virtual Ethernet links.

Follow the [official Containerlab installation guide](https://containerlab.dev/install/) rather than copying an unreviewed installer from this repository.

## Deploy

```bash
git clone https://github.com/JohnnyZLi/OSPF-Resiliency-Lab.git
cd OSPF-Resiliency-Lab
make deploy
```

Containerlab creates four containers named:

- `clab-ospf-resilience-edge-west`
- `clab-ospf-resilience-core-a`
- `clab-ospf-resilience-core-b`
- `clab-ospf-resilience-edge-east`

## Inspect manually

```bash
docker exec -it clab-ospf-resilience-edge-west vtysh
```

Useful FRR commands:

```text
show ip ospf neighbor
show ip route 10.255.0.4/32
show ip ospf database
show running-config
```

## Run the failure test

```bash
make verify
```

The test pauses and unpauses only the lab's `core-a` container. It writes host-specific evidence to `evidence/latest-run.json`.

To validate baseline routing without injecting a failure:

```bash
python3 scripts/verify_lab.py --skip-failure
```

## Clean up

```bash
make destroy
```

If a verification command is interrupted while `core-a` is paused, restore it before continuing:

```bash
docker unpause clab-ospf-resilience-core-a
```
