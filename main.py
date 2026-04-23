from scapy.all import sniff, IP, TCP, UDP, ICMP
from collections import defaultdict
from colorama import Fore, init

init(autoreset=True)

# Statistics storage
stats = defaultdict(int)
total_packets = 0

def classify_packet(packet):
    global total_packets
    total_packets += 1

    if packet.haslayer(TCP):
        stats['TCP'] += 1
        print(Fore.GREEN + "[TCP] Packet Captured")

    elif packet.haslayer(UDP):
        stats['UDP'] += 1
        print(Fore.BLUE + "[UDP] Packet Captured")

    elif packet.haslayer(ICMP):
        stats['ICMP'] += 1
        print(Fore.YELLOW + "[ICMP] Packet Captured")

    else:
        stats['OTHER'] += 1
        print(Fore.RED + "[OTHER] Packet Captured")

def show_stats():
    print("\n===== Traffic Statistics =====")
    for protocol, count in stats.items():
        percentage = (count / total_packets) * 100 if total_packets else 0
        print(f"{protocol}: {count} packets ({percentage:.2f}%)")
    print("==============================\n")

def main():
    print("Starting Traffic Classification System...")
    print("Press Ctrl+C to stop and view results.\n")

    try:
        sniff(prn=classify_packet, store=False)
    except KeyboardInterrupt:
        print("\nStopping capture...")
        show_stats()

if __name__ == "__main__":
    main()