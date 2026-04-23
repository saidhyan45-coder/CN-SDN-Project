#!/usr/bin/env python3
"""Ryu controller for the Traffic Classification System.

This controller behaves like a simple OpenFlow 1.3 learning switch and also
classifies traffic into TCP, UDP, and ICMP. It prints live protocol counts and
percentages in the terminal, and can optionally log the results to a file.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import icmp
from ryu.lib.packet import ipv4
from ryu.lib.packet import packet
from ryu.lib.packet import tcp
from ryu.lib.packet import udp
from ryu.ofproto import ofproto_v1_3


class TrafficClassificationController(app_manager.RyuApp):
    """OpenFlow 1.3 controller that classifies traffic by protocol."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = defaultdict(dict)
        self.datapaths = {}
        self.protocol_packet_counts = {"TCP": 0, "UDP": 0, "ICMP": 0}
        self.flow_packet_totals = defaultdict(int)
        self.log_file = "traffic_stats.log"
        self.monitor_thread = hub.spawn(self._monitor)

        file_handler = logging.FileHandler(self.log_file)
        file_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
        self.logger.addHandler(file_handler)
        self.logger.info("Traffic Classification Controller started")

    def _protocol_percentages(self):
        total = sum(self.protocol_packet_counts.values())
        if total == 0:
            return {name: 0.0 for name in self.protocol_packet_counts}
        return {
            name: (count / total) * 100
            for name, count in self.protocol_packet_counts.items()
        }

    def _print_protocol_summary(self):
        percentages = self._protocol_percentages()
        print("\nTraffic Distribution")
        print("=" * 40)
        for protocol in ("TCP", "UDP", "ICMP"):
            count = self.protocol_packet_counts[protocol]
            percentage = percentages[protocol]
            print(f"{protocol}: {count} packets ({percentage:.2f}%)")
        print("=" * 40)

        self.logger.info(
            "TCP=%s UDP=%s ICMP=%s",
            self.protocol_packet_counts["TCP"],
            self.protocol_packet_counts["UDP"],
            self.protocol_packet_counts["ICMP"],
        )
        self._save_plot()

    def _detect_protocol(self, pkt):
        """Identify the transport protocol from a packet."""
        if pkt.get_protocol(tcp.tcp):
            return "TCP"
        if pkt.get_protocol(udp.udp):
            return "UDP"
        if pkt.get_protocol(icmp.icmp):
            return "ICMP"
        return None

    def _build_flow_key(self, src_ip, dst_ip, protocol):
        """Create a stable key used for counting packets per flow."""
        return protocol, src_ip, dst_ip

    def _save_plot(self):
        """Optionally save a bar chart whenever statistics change."""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            return

        labels = ["TCP", "UDP", "ICMP"]
        values = [self.protocol_packet_counts[label] for label in labels]
        colors = ["#2563eb", "#f59e0b", "#16a34a"]

        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(labels, values, color=colors)
        ax.set_title("Traffic Distribution")
        ax.set_xlabel("Protocol")
        ax.set_ylabel("Packet Count")
        fig.tight_layout()
        fig.savefig("traffic_distribution.png")
        plt.close(fig)

    def _monitor(self):
        """Poll switches periodically to update packet counters from flow stats."""
        while True:
            for datapath in list(self.datapaths.values()):
                self._request_flow_stats(datapath)
            hub.sleep(2)

    def _request_flow_stats(self, datapath):
        parser = datapath.ofproto_parser
        request = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(request)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        """Install a flow entry in the switch."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        instructions = [
            parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)
        ]

        if buffer_id is not None:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                buffer_id=buffer_id,
                priority=priority,
                match=match,
                instructions=instructions,
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=instructions,
            )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Install table-miss flow so unknown packets reach the controller."""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        self.add_flow(datapath, priority=0, match=match, actions=actions)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        """Track connected switches so they can be polled for flow statistics."""
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER and datapath.id in self.datapaths:
            del self.datapaths[datapath.id]

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """Handle first packets of flows, classify them, and install rules."""
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dpid = datapath.id
        src_mac = eth.src
        dst_mac = eth.dst

        self.mac_to_port[dpid][src_mac] = in_port

        if dst_mac in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst_mac]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        protocol = self._detect_protocol(pkt)

        if out_port != ofproto.OFPP_FLOOD and ip_pkt and protocol:
            if protocol == "TCP":
                ip_proto = 6
            elif protocol == "UDP":
                ip_proto = 17
            else:
                ip_proto = 1

            match = parser.OFPMatch(
                in_port=in_port,
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_src=ip_pkt.src,
                ipv4_dst=ip_pkt.dst,
                ip_proto=ip_proto,
            )
            self.add_flow(datapath, priority=10, match=match, actions=actions, buffer_id=msg.buffer_id)

            self.logger.info(
                "Installed %s flow: %s -> %s on switch %s",
                protocol,
                ip_pkt.src,
                ip_pkt.dst,
                dpid,
            )
            return

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

        if protocol:
            self.logger.info(
                "Packet-In classified as %s from %s to %s",
                protocol,
                ip_pkt.src if ip_pkt else "unknown",
                ip_pkt.dst if ip_pkt else "unknown",
            )

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        """Update per-protocol counters using switch flow statistics."""
        updated = False

        for stat in ev.msg.body:
            match = stat.match

            if match.get("eth_type") != ether_types.ETH_TYPE_IP:
                continue

            src_ip = match.get("ipv4_src")
            dst_ip = match.get("ipv4_dst")
            ip_proto = match.get("ip_proto")

            if not src_ip or not dst_ip or ip_proto not in (1, 6, 17):
                continue

            if ip_proto == 6:
                protocol = "TCP"
            elif ip_proto == 17:
                protocol = "UDP"
            else:
                protocol = "ICMP"

            flow_key = self._build_flow_key(src_ip, dst_ip, protocol)
            packet_total = stat.packet_count
            previous_total = self.flow_packet_totals[flow_key]

            if packet_total > previous_total:
                self.protocol_packet_counts[protocol] += packet_total - previous_total
                self.flow_packet_totals[flow_key] = packet_total
                updated = True

        if updated:
            self._print_protocol_summary()
