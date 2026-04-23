#!/usr/bin/env python3
"""Mininet topology for the Traffic Classification System.

Topology:
    h1 --- s1 --- h2
    h3 ---/
    h4 ---/

Use this script with a remote Ryu controller running on 127.0.0.1:6653.
"""

from __future__ import annotations

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo


class TrafficClassificationTopo(Topo):
    """Simple star topology with one OpenFlow switch and four hosts."""

    def build(self):
        switch = self.addSwitch("s1", protocols="OpenFlow13")

        hosts = [
            self.addHost("h1", ip="10.0.0.1/24"),
            self.addHost("h2", ip="10.0.0.2/24"),
            self.addHost("h3", ip="10.0.0.3/24"),
            self.addHost("h4", ip="10.0.0.4/24"),
        ]

        for host in hosts:
            self.addLink(host, switch, cls=TCLink, bw=10, delay="5ms")


def print_host_ips(net):
    info("\nHost IP addresses:\n")
    for host in net.hosts:
        info(f"  {host.name}: {host.IP()}\n")


def run_demo_commands(net):
    """Show ready-to-run traffic commands for students."""
    info("\nSuggested traffic commands inside Mininet CLI:\n")
    info("  h2 iperf -s &\n")
    info("  h1 iperf -c 10.0.0.2 -t 10\n")
    info("  h4 iperf -s -u &\n")
    info("  h3 iperf -c 10.0.0.4 -u -b 5M -t 10\n")
    info("  h1 ping -c 5 10.0.0.3\n")
    info("  pingall\n")


def start_network():
    topo = TrafficClassificationTopo()
    controller = RemoteController("c0", ip="127.0.0.1", port=6653)

    net = Mininet(
        topo=topo,
        controller=controller,
        switch=OVSSwitch,
        autoSetMacs=True,
        autoStaticArp=True,
    )

    info("*** Starting network\n")
    net.start()

    print_host_ips(net)
    run_demo_commands(net)
    info("\nEntering Mininet CLI. Generate TCP, UDP, and ICMP traffic now.\n")
    CLI(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    start_network()
