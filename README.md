# Traffic Classification System

This project demonstrates traffic classification in Software Defined Networking
(SDN) using:

- `Mininet` for network emulation
- `Ryu` as the remote SDN controller
- `OpenFlow 1.3` for switch-controller communication

The controller identifies traffic as `TCP`, `UDP`, or `ICMP`, maintains packet
statistics, prints real-time protocol distribution, and optionally saves a bar
chart image.

## Project Files

- `topology.py` - Mininet topology with 1 switch and 4 hosts
- `controller.py` - Ryu controller with traffic classification logic
- `requirements.txt` - Python packages used by the controller

## Topology Used

One OpenFlow switch connects four hosts:

- `h1` - `10.0.0.1`
- `h2` - `10.0.0.2`
- `h3` - `10.0.0.3`
- `h4` - `10.0.0.4`

The switch connects to a remote controller on `127.0.0.1:6653`.

## How Traffic Is Classified

The Ryu controller receives packets through `Packet-In` events when the switch
does not yet know how to forward them.

Classification steps:

1. The controller reads the incoming packet.
2. It checks whether the IPv4 payload contains:
   - `TCP`
   - `UDP`
   - `ICMP`
3. It learns MAC addresses like a learning switch.
4. Once the destination is known, it installs an OpenFlow 1.3 flow rule for
   that traffic so later packets are forwarded directly by the switch.
5. The controller periodically asks the switch for flow statistics.
6. Packet counters from flow statistics are added to protocol totals.
7. The controller prints clean live output such as:

```text
TCP: 120 packets (50.00%)
UDP: 60 packets (25.00%)
ICMP: 60 packets (25.00%)
```

This avoids repeated flooding after the first packets while still keeping
protocol statistics updated.

## Prerequisites

You need these tools installed on a Linux machine or VM:

- Python 3
- Mininet
- Open vSwitch
- Ryu
- `iperf` or `iperf3`

### Install Python packages

```bash
pip install -r requirements.txt
```

### Typical Ubuntu packages

```bash
sudo apt update
sudo apt install mininet openvswitch-switch iperf
```

If `iperf` is not available, some systems provide `iperf3`. For easiest use
with the commands below, `iperf` is preferred.

## How To Run

Open two terminals.

### Terminal 1: Start the Ryu controller

```bash
ryu-manager controller.py
```

You should see the controller waiting for the switch connection.

### Terminal 2: Start the Mininet topology

```bash
sudo python3 topology.py
```

This opens the Mininet CLI after creating the topology.

## Generate Traffic

Run these commands inside the Mininet CLI.

### 1. Generate TCP traffic

Start a TCP server on `h2`:

```bash
mininet> h2 iperf -s &
```

Send TCP traffic from `h1` to `h2`:

```bash
mininet> h1 iperf -c 10.0.0.2 -t 10
```

### 2. Generate UDP traffic

Start a UDP server on `h4`:

```bash
mininet> h4 iperf -s -u &
```

Send UDP traffic from `h3` to `h4`:

```bash
mininet> h3 iperf -c 10.0.0.4 -u -b 5M -t 10
```

### 3. Generate ICMP traffic

Send ping traffic from `h1` to `h3`:

```bash
mininet> h1 ping -c 5 10.0.0.3
```

### Optional connectivity test

```bash
mininet> pingall
```

## Expected Controller Output

The controller prints live statistics in the terminal:

```text
Traffic Distribution
========================================
TCP: 120 packets (50.00%)
UDP: 60 packets (25.00%)
ICMP: 60 packets (25.00%)
========================================
```

It also writes:

- `traffic_stats.log` - protocol summary log
- `traffic_distribution.png` - bar chart image if `matplotlib` is installed

## Viva Explanation

### Why Packet-In is used

When a packet does not match any flow rule in the switch, the switch sends it to
the controller using a `Packet-In` event. This lets the controller inspect the
packet and decide how to handle future packets of the same type.

### Why flow rules are installed

After learning the destination and protocol, the controller installs a flow rule
so the switch forwards later packets directly. This reduces controller load and
prevents unnecessary flooding.

### How statistics are maintained

The controller stores protocol counters in a Python dictionary:

```python
{"TCP": 0, "UDP": 0, "ICMP": 0}
```

Then it periodically requests flow statistics from the switch and updates the
counter values based on packet counts seen for each installed flow.

## Notes

- Run `sudo mn -c` before restarting Mininet if an old topology is still active.
- This project is intentionally simple and written for student understanding.
- The controller focuses on IPv4 TCP, UDP, and ICMP traffic.
