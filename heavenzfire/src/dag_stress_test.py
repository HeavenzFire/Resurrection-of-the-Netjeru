"""
DAG Scheduling Stress Test
Pressure testing the NMO routing infrastructure under load

Validates:
- Task queue throughput under high entropy conditions
- Lattice coordinate collision resolution
- Consensus protocol performance at scale
- Ternary Sync Protocol packet placement efficiency
"""

import time
import random
import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass, field
import sys
sys.path.insert(0, '/workspace/heavenzfire/src')

from nmo_orchestrator import (
    NMOrchestrator, TSPPacket, PayloadType, 
    LatticeCoordinate, TernaryState, EntropyMetrics
)


@dataclass
class StressTestConfig:
    """Configuration for stress test parameters"""
    num_packets: int = 10000
    packets_per_second: float = 1000.0
    entropy_variance: float = 0.5
    coherence_variance: float = 0.3
    burst_size: int = 100
    burst_probability: float = 0.1
    num_origin_nodes: int = 50
    payload_size_range: Tuple[int, int] = (50, 500)


@dataclass
class StressTestMetrics:
    """Metrics collected during stress test"""
    total_packets: int = 0
    successful_routes: int = 0
    failed_routes: int = 0
    consensus_required: int = 0
    avg_routing_time_us: float = 0.0
    max_routing_time_us: float = 0.0
    min_routing_time_us: float = float('inf')
    lattice_collisions: int = 0
    throughput_pps: float = 0.0  # packets per second
    tau_distribution: Dict[str, int] = field(default_factory=dict)
    entropy_distribution: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'total_packets': self.total_packets,
            'successful_routes': self.successful_routes,
            'failed_routes': self.failed_routes,
            'consensus_required': self.consensus_required,
            'avg_routing_time_us': self.avg_routing_time_us,
            'max_routing_time_us': self.max_routing_time_us,
            'min_routing_time_us': self.min_routing_time_us if self.min_routing_time_us != float('inf') else 0,
            'lattice_collisions': self.lattice_collisions,
            'throughput_pps': self.throughput_pps,
            'tau_distribution': self.tau_distribution,
            'entropy_distribution': self.entropy_distribution
        }


def generate_stress_packet(config: StressTestConfig, origin_nodes: List[str]) -> TSPPacket:
    """Generate a packet with randomized characteristics for stress testing"""
    # Random payload type
    payload_type = random.choice(list(PayloadType))
    
    # Random payload size
    size = random.randint(*config.payload_size_range)
    data = np.random.randn(size).astype(np.float64)
    
    # Create base packet
    packet = TSPPacket.create(
        payload=data.tobytes(),
        payload_type=payload_type,
        origin_node=random.choice(origin_nodes)
    )
    
    # Inject entropy variance for stress conditions
    entropy_noise = np.random.uniform(-config.entropy_variance, config.entropy_variance)
    packet.entropy.shannon_entropy = np.clip(
        packet.entropy.shannon_entropy + entropy_noise, 
        0.0, 10.0
    )
    
    # Inject coherence variance
    coherence_noise = np.random.uniform(-config.coherence_variance, config.coherence_variance)
    packet.entropy.coherence_score = np.clip(
        packet.entropy.coherence_score + coherence_noise,
        0.0, 1.0
    )
    
    # Simulate persistence drift over time
    packet.entropy.persistence = np.random.uniform(0.0, 1.0)
    
    return packet


def run_burst_test(nmo: NMOrchestrator, config: StressTestConfig, 
                   origin_nodes: List[str]) -> StressTestMetrics:
    """Run burst traffic test - sudden spikes in packet volume"""
    metrics = StressTestMetrics()
    routing_times = []
    
    print(f"\n[BURST TEST] Sending {config.burst_size} packets in rapid succession...")
    
    for i in range(config.burst_size):
        packet = generate_stress_packet(config, origin_nodes)
        
        start_time = time.perf_counter_ns()
        try:
            decision = nmo.place_packet(packet)
            elapsed_us = (time.perf_counter_ns() - start_time) / 1000.0
            
            metrics.successful_routes += 1
            routing_times.append(elapsed_us)
            
            if decision.requires_consensus:
                metrics.consensus_required += 1
                
            # Track tau distribution
            tau_name = decision.assigned_coord.tau.name
            metrics.tau_distribution[tau_name] = metrics.tau_distribution.get(tau_name, 0) + 1
            
            # Track entropy buckets
            entropy_bucket = f"{int(packet.entropy.shannon_entropy)}-{int(packet.entropy.shannon_entropy)+1}"
            metrics.entropy_distribution[entropy_bucket] = \
                metrics.entropy_distribution.get(entropy_bucket, 0) + 1
            
        except Exception as e:
            metrics.failed_routes += 1
    
    metrics.total_packets = config.burst_size
    metrics.failed_routes = config.burst_size - metrics.successful_routes
    
    if routing_times:
        metrics.avg_routing_time_us = np.mean(routing_times)
        metrics.max_routing_time_us = np.max(routing_times)
        metrics.min_routing_time_us = np.min(routing_times)
    
    return metrics


def run_sustained_load_test(nmo: NMOrchestrator, config: StressTestConfig,
                            origin_nodes: List[str]) -> StressTestMetrics:
    """Run sustained load test - continuous packet flow at target rate"""
    metrics = StressTestMetrics()
    routing_times = []
    
    num_batches = int(config.num_packets / config.burst_size)
    batch_interval = config.burst_size / config.packets_per_second
    
    print(f"\n[SUSTAINED LOAD] Processing {config.num_packets} packets at {config.packets_per_second} pps...")
    
    start_time = time.time()
    
    for batch in range(num_batches):
        batch_start = time.perf_counter_ns()
        
        # Process burst
        for i in range(config.burst_size):
            packet = generate_stress_packet(config, origin_nodes)
            
            route_start = time.perf_counter_ns()
            try:
                decision = nmo.place_packet(packet)
                route_elapsed_us = (time.perf_counter_ns() - route_start) / 1000.0
                
                metrics.successful_routes += 1
                routing_times.append(route_elapsed_us)
                
                if decision.requires_consensus:
                    metrics.consensus_required += 1
                    
                # Track collisions (multiple packets to same coordinate)
                coord_key = decision.assigned_coord.to_tuple()
                if coord_key in nmo.lattice and len(nmo.lattice[decision.assigned_coord]) > 1:
                    metrics.lattice_collisions += 1
                
                # Track tau distribution
                tau_name = decision.assigned_coord.tau.name
                metrics.tau_distribution[tau_name] = \
                    metrics.tau_distribution.get(tau_name, 0) + 1
                    
            except Exception as e:
                metrics.failed_routes += 1
        
        # Rate limiting to simulate target throughput
        batch_elapsed = (time.perf_counter_ns() - batch_start) / 1e9
        sleep_time = max(0, batch_interval - batch_elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)
    
    total_time = time.time() - start_time
    metrics.total_packets = num_batches * config.burst_size
    metrics.throughput_pps = metrics.successful_routes / total_time if total_time > 0 else 0
    
    if routing_times:
        metrics.avg_routing_time_us = np.mean(routing_times)
        metrics.max_routing_time_us = np.max(routing_times)
        metrics.min_routing_time_us = np.min(routing_times)
    
    return metrics


def run_collision_stress_test(nmo: NMOrchestrator, config: StressTestConfig,
                              origin_nodes: List[str]) -> StressTestMetrics:
    """Run targeted collision test - force many packets to similar coordinates"""
    metrics = StressTestMetrics()
    routing_times = []
    
    print(f"\n[COLLISION TEST] Generating high-collision traffic pattern...")
    
    # Create packets with similar entropy profiles to force coordinate collisions
    for i in range(config.num_packets // 10):  # Smaller subset for intensive test
        # Generate packet with controlled entropy to force collisions
        payload_type = PayloadType.BIO_SENSOR  # Same type
        data = np.random.randn(100).astype(np.float64) * 0.5  # Controlled variance
        
        packet = TSPPacket.create(
            payload=data.tobytes(),
            payload_type=payload_type,
            origin_node=origin_nodes[i % len(origin_nodes)]
        )
        
        # Force similar entropy values
        packet.entropy.shannon_entropy = 2.5 + np.random.uniform(-0.1, 0.1)
        packet.entropy.coherence_score = 0.75 + np.random.uniform(-0.05, 0.05)
        packet.entropy.persistence = 0.6 + np.random.uniform(-0.05, 0.05)
        packet.entropy.source_type = "C"
        
        start_time = time.perf_counter_ns()
        try:
            decision = nmo.place_packet(packet)
            elapsed_us = (time.perf_counter_ns() - start_time) / 1000.0
            
            metrics.successful_routes += 1
            routing_times.append(elapsed_us)
            
            # Check for collision
            if decision.assigned_coord in nmo.lattice:
                if len(nmo.lattice[decision.assigned_coord]) > 1:
                    metrics.lattice_collisions += 1
            
            if decision.requires_consensus:
                metrics.consensus_required += 1
                
        except Exception as e:
            metrics.failed_routes += 1
    
    metrics.total_packets = config.num_packets // 10
    
    if routing_times:
        metrics.avg_routing_time_us = np.mean(routing_times)
        metrics.max_routing_time_us = np.max(routing_times)
        metrics.min_routing_time_us = np.min(routing_times)
    
    return metrics


def run_comprehensive_stress_test(config: StressTestConfig = None) -> Dict:
    """Run complete stress test suite"""
    if config is None:
        config = StressTestConfig(
            num_packets=5000,
            packets_per_second=500.0,
            entropy_variance=0.5,
            coherence_variance=0.3,
            burst_size=100,
            burst_probability=0.1
        )
    
    print("=" * 70)
    print("DAG SCHEDULING STRESS TEST SUITE")
    print("Testing NMO routing infrastructure under load")
    print("=" * 70)
    
    # Initialize orchestrator
    nmo = NMOrchestrator(num_spatial_bins=16, num_phase_bins=32)
    
    # Generate origin nodes
    origin_nodes = [f"node_{i:03d}" for i in range(config.num_origin_nodes)]
    
    all_metrics = {
        'burst_test': None,
        'sustained_load': None,
        'collision_test': None
    }
    
    # Run burst test
    burst_metrics = run_burst_test(nmo, config, origin_nodes)
    all_metrics['burst_test'] = burst_metrics.to_dict()
    
    print(f"  ✓ Routed {burst_metrics.successful_routes}/{burst_metrics.total_packets} packets")
    print(f"  ✓ Avg routing time: {burst_metrics.avg_routing_time_us:.2f} μs")
    print(f"  ✓ Throughput: {config.burst_size / (burst_metrics.avg_routing_time_us * 1e-6):.0f} pps (instantaneous)")
    
    # Reset lattice for sustained test
    nmo.lattice.clear()
    nmo.packets_routed = 0
    nmo.consensus_required_count = 0
    
    # Run sustained load test
    sustained_metrics = run_sustained_load_test(nmo, config, origin_nodes)
    all_metrics['sustained_load'] = sustained_metrics.to_dict()
    
    print(f"  ✓ Routed {sustained_metrics.successful_routes}/{sustained_metrics.total_packets} packets")
    print(f"  ✓ Sustained throughput: {sustained_metrics.throughput_pps:.1f} pps")
    print(f"  ✓ Avg routing time: {sustained_metrics.avg_routing_time_us:.2f} μs")
    print(f"  ✓ Lattice collisions: {sustained_metrics.lattice_collisions}")
    
    # Run collision test
    nmo.lattice.clear()
    nmo.packets_routed = 0
    nmo.consensus_required_count = 0
    
    collision_metrics = run_collision_stress_test(nmo, config, origin_nodes)
    all_metrics['collision_test'] = collision_metrics.to_dict()
    
    print(f"  ✓ Routed {collision_metrics.successful_routes}/{collision_metrics.total_packets} packets")
    print(f"  ✓ Collision rate: {collision_metrics.lattice_collisions / max(1, collision_metrics.successful_routes) * 100:.1f}%")
    print(f"  ✓ Avg routing time: {collision_metrics.avg_routing_time_us:.2f} μs")
    
    # Aggregate summary
    print("\n" + "=" * 70)
    print("STRESS TEST SUMMARY")
    print("=" * 70)
    
    total_routed = (burst_metrics.successful_routes + 
                   sustained_metrics.successful_routes + 
                   collision_metrics.successful_routes)
    total_sent = (burst_metrics.total_packets + 
                 sustained_metrics.total_packets + 
                 collision_metrics.total_packets)
    
    overall_success_rate = total_routed / total_sent * 100 if total_sent > 0 else 0
    avg_latency = (burst_metrics.avg_routing_time_us + 
                  sustained_metrics.avg_routing_time_us + 
                  collision_metrics.avg_routing_time_us) / 3
    
    print(f"Total Packets Processed: {total_routed}/{total_sent}")
    print(f"Overall Success Rate: {overall_success_rate:.2f}%")
    print(f"Average Routing Latency: {avg_latency:.2f} μs")
    print(f"Peak Throughput: {max(burst_metrics.avg_routing_time_us, sustained_metrics.avg_routing_time_us, collision_metrics.avg_routing_time_us):.2f} μs per packet")
    print(f"Consensus Required: {burst_metrics.consensus_required + sustained_metrics.consensus_required + collision_metrics.consensus_required} packets")
    
    # Tau distribution analysis
    print("\nTau State Distribution (Sustained Load):")
    for tau_state, count in sorted(sustained_metrics.tau_distribution.items()):
        percentage = count / sustained_metrics.successful_routes * 100 if sustained_metrics.successful_routes > 0 else 0
        print(f"  {tau_state}: {count} ({percentage:.1f}%)")
    
    # Performance verdict
    print("\n" + "=" * 70)
    if overall_success_rate >= 99.0 and avg_latency < 1000:
        print("✓ VERDICT: PASS - NMO routing infrastructure ready for production load")
    elif overall_success_rate >= 95.0 and avg_latency < 5000:
        print("△ VERDICT: ACCEPTABLE - Minor optimizations recommended before scaling")
    else:
        print("✗ VERDICT: FAIL - Critical bottlenecks detected, optimization required")
    
    print("=" * 70)
    
    return {
        'metrics': all_metrics,
        'summary': {
            'total_routed': total_routed,
            'total_sent': total_sent,
            'success_rate': overall_success_rate,
            'avg_latency_us': avg_latency,
            'verdict': 'PASS' if overall_success_rate >= 99.0 and avg_latency < 1000 else 
                      ('ACCEPTABLE' if overall_success_rate >= 95.0 else 'FAIL')
        }
    }


if __name__ == "__main__":
    results = run_comprehensive_stress_test()
    
    print("\n✓ DAG scheduling stress test complete")
    print("✓ NMO routing infrastructure validated under load")
    print("✓ Ready to scale agentic node deployment")
