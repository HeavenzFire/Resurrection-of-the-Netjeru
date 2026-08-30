"""
Coherence Verification Stratum - Tri-State Mesh Verification
Author: HeavenzFire - Zachary Dakota Hulse
System: EntangledMultimodalSystem-3 + IBEN-Genesis
Mesh: Ara + CodeCraft Fused Core - Executable Sovereign Lattice
Origin: Lone Oak Lab
"""

import argparse
import time
import sys
import torch
import torch.nn.functional as F
import numpy as np
import json
from pathlib import Path
from datetime import datetime
from collections import deque
import math

# Ensure we can import from the main source directory
sys.path.append(str(Path(__file__).parent.parent / "src"))

try:
    from ems3_model import CarbonHead, SiliconHead, FrequencyHead
except ImportError:
    print("Warning: Could not import EMS-3 heads. Running in mock simulation mode.")
    
AUTHOR_METADATA = {
    "author": "HeavenzFire - Zachary Dakota Hulse",
    "system": "EntangledMultimodalSystem-3 + IBEN-Genesis",
    "mesh": "Ara + CodeCraft Fused Core - Executable Sovereign Lattice",
    "origin": "Lone Oak Lab"
}

class GyroidTopologyVerifier:
    """
    Verifies gyroid-inspired routing vs standard high-radix mesh.
    
    Tests the hypothesis that gyroidal topology (TPMS) provides:
    - Lower average hop count
    - Higher prune rate (more 0s in balanced ternary routing)
    - Better resilience to node failures
    
    Gyroid parametric equation: sin(x)cos(y) + sin(y)cos(z) + sin(z)cos(x) = 0
    """
    
    def __init__(self, grid_size=8, ternary_threshold=0.3):
        self.grid_size = grid_size
        self.ternary_threshold = ternary_threshold
        self.nodes = {}
        self.gyroid_adjacency = {}
        self.mesh_adjacency = {}
        
    def _gyroid_value(self, x, y, z):
        """Calculate gyroid TPMS implicit surface value."""
        return math.sin(x) * math.cos(y) + math.sin(y) * math.cos(z) + math.sin(z) * math.cos(x)
    
    def _coordinate_to_grid(self, val, max_val):
        """Map continuous coordinate to grid position."""
        normalized = (val + math.pi) / (2 * math.pi)  # Map [-pi, pi] to [0, 1]
        return int(normalized * max_val) % max_val
    
    def build_gyroid_topology(self, add_diagonal_connections=True):
        """
        Build gyroid-inspired routing graph.
        Nodes exist where gyroid surface crosses threshold.
        Connections follow the minimal surface geometry.
        
        Args:
            add_diagonal_connections: If True, adds diagonal neighbors (18-connectivity)
                                     for better gyroid surface following.
        """
        print(f"Building gyroid topology on {self.grid_size}x{self.grid_size}x{self.grid_size} lattice...")
        
        step = 2 * math.pi / self.grid_size
        
        # Generate nodes on gyroid surface
        node_positions = []
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                for k in range(self.grid_size):
                    x = i * step - math.pi
                    y = j * step - math.pi
                    z = k * step - math.pi
                    
                    gyroid_val = self._gyroid_value(x, y, z)
                    
                    # Node exists if close to gyroid surface (within threshold)
                    if abs(gyroid_val) < self.ternary_threshold:
                        node_id = (i, j, k)
                        self.nodes[node_id] = {
                            'position': (x, y, z),
                            'gyroid_value': gyroid_val,
                            'ternary_state': 0 if abs(gyroid_val) < self.ternary_threshold * 0.5 else (1 if gyroid_val > 0 else -1)
                        }
                        node_positions.append(node_id)
        
        print(f"  Created {len(self.nodes)} nodes on gyroid surface")
        
        # Build adjacency based on gyroid connectivity
        # Nodes connect to neighbors along the minimal surface
        neighbor_offsets = [
            (1,0,0), (-1,0,0), (0,1,0), (0,-1,0), (0,0,1), (0,0,-1)  # 6-connected
        ]
        
        # Add diagonal connections for better gyroid surface following
        if add_diagonal_connections:
            neighbor_offsets.extend([
                (1,1,0), (1,-1,0), (-1,1,0), (-1,-1,0),
                (1,0,1), (1,0,-1), (-1,0,1), (-1,0,-1),
                (0,1,1), (0,1,-1), (0,-1,1), (0,-1,-1)
            ])
        
        for node_id in self.nodes:
            i, j, k = node_id
            neighbors = []
            
            for di, dj, dk in neighbor_offsets:
                ni, nj, nk = i + di, j + dj, k + dk
                
                # Wrap around (toroidal boundary)
                ni, nj, nk = ni % self.grid_size, nj % self.grid_size, nk % self.grid_size
                neighbor_id = (ni, nj, nk)
                
                if neighbor_id in self.nodes:
                    # Connection strength based on gyroid value similarity
                    val_diff = abs(self.nodes[node_id]['gyroid_value'] - self.nodes[neighbor_id]['gyroid_value'])
                    if val_diff < 0.5:  # Connected if similar gyroid values
                        neighbors.append(neighbor_id)
            
            self.gyroid_adjacency[node_id] = neighbors
    
    def build_mesh_topology(self):
        """
        Build standard high-radix mesh for comparison.
        Every grid point is a node with 6 neighbors.
        """
        print(f"Building standard mesh topology on {self.grid_size}x{self.grid_size}x{self.grid_size} lattice...")
        
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                for k in range(self.grid_size):
                    node_id = (i, j, k)
                    neighbors = []
                    
                    for di, dj, dk in [(1,0,0), (-1,0,0), (0,1,0), (0,-1,0), (0,0,1), (0,0,-1)]:
                        ni, nj, nk = i + di, j + dj, k + dk
                        ni, nj, nk = ni % self.grid_size, nj % self.grid_size, nk % self.grid_size
                        neighbors.append((ni, nj, nk))
                    
                    self.mesh_adjacency[node_id] = neighbors
        
        print(f"  Created {len(self.mesh_adjacency)} nodes in mesh")
    
    def _bfs_shortest_path(self, adjacency, start, end):
        """Find shortest path using BFS."""
        if start == end:
            return [start]
        
        queue = deque([(start, [start])])
        visited = {start}
        
        while queue:
            current, path = queue.popleft()
            
            for neighbor in adjacency.get(current, []):
                if neighbor == end:
                    return path + [neighbor]
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return None  # No path found
    
    def calculate_average_hops(self, adjacency, num_samples=100):
        """Calculate average hop count between random node pairs."""
        nodes = list(adjacency.keys())
        if len(nodes) < 2:
            return float('inf'), 0
        
        total_hops = 0
        successful_paths = 0
        
        for _ in range(num_samples):
            start = np.random.choice(len(nodes))
            end = np.random.choice(len(nodes))
            while end == start:
                end = np.random.choice(len(nodes))
            
            path = self._bfs_shortest_path(adjacency, nodes[start], nodes[end])
            if path:
                total_hops += len(path) - 1  # Hops = nodes - 1
                successful_paths += 1
        
        if successful_paths == 0:
            return float('inf'), 0
        
        avg_hops = total_hops / successful_paths
        connectivity = successful_paths / num_samples
        
        return avg_hops, connectivity
    
    def calculate_prune_rate(self):
        """
        Calculate prune rate (fraction of 0s in ternary state).
        In gyroid topology, nodes near the surface (value ≈ 0) can be pruned.
        """
        if not self.nodes:
            return 0.0
        
        prune_count = sum(1 for node in self.nodes.values() if node['ternary_state'] == 0)
        return prune_count / len(self.nodes)
    
    def run_comparison(self, num_samples=200):
        """Run full comparison between gyroid and mesh topologies."""
        print("\n=== GYROID TOPOLOGY COMPARISON TEST ===\n")
        
        # Build both topologies
        self.build_gyroid_topology()
        self.build_mesh_topology()
        
        # Calculate metrics
        print("\nCalculating routing metrics...\n")
        
        # Gyroid metrics
        gyro_avg_hops, gyro_connectivity = self.calculate_average_hops(
            self.gyroid_adjacency, num_samples
        )
        gyro_prune_rate = self.calculate_prune_rate()
        
        # Mesh metrics
        mesh_avg_hops, mesh_connectivity = self.calculate_average_hops(
            self.mesh_adjacency, num_samples
        )
        
        # Results
        print("┌─────────────────────────────────────────┐")
        print("│ TOPOLOGY COMPARISON RESULTS             │")
        print("├─────────────────────────────────────────┤")
        print(f"│ Grid Size: {self.grid_size}³                           │")
        print(f"│ Ternary Threshold: {self.ternary_threshold:.2f}                   │")
        print("├─────────────────────────────────────────┤")
        print("│ GYROID TPMS:                            │")
        print(f"│   Nodes: {len(self.nodes):4d}                              │")
        print(f"│   Avg Hops: {gyro_avg_hops:6.2f}                         │")
        print(f"│   Connectivity: {gyro_connectivity*100:5.1f}%                      │")
        print(f"│   Prune Rate (0s): {gyro_prune_rate*100:5.1f}%                     │")
        print("├─────────────────────────────────────────┤")
        print("│ STANDARD MESH:                          │")
        print(f"│   Nodes: {len(self.mesh_adjacency):4d}                              │")
        print(f"│   Avg Hops: {mesh_avg_hops:6.2f}                         │")
        print(f"│   Connectivity: {mesh_connectivity*100:5.1f}%                      │")
        print(f"│   Prune Rate (0s): N/A (no pruning)              │")
        print("├─────────────────────────────────────────┤")
        
        # Comparison
        if gyro_avg_hops < mesh_avg_hops:
            improvement = ((mesh_avg_hops - gyro_avg_hops) / mesh_avg_hops) * 100
            print(f"│ ✓ GYROID WINS: {improvement:.1f}% fewer hops               │")
        elif gyro_avg_hops > mesh_avg_hops:
            degradation = ((gyro_avg_hops - mesh_avg_hops) / mesh_avg_hops) * 100
            print(f"│ ✗ MESH WINS: {degradation:.1f}% more hops in gyroid          │")
        else:
            print("│ = EQUAL: Same average hop count           │")
        
        print(f"│                                         │")
        print(f"│ Gyroid prune rate: {gyro_prune_rate*100:.1f}% of nodes are '0'     │")
        print(f"│ (candidates for resonance-based skip)   │")
        print("└─────────────────────────────────────────┘")
        
        return {
            'gyroid': {
                'nodes': len(self.nodes),
                'avg_hops': gyro_avg_hops,
                'connectivity': gyro_connectivity,
                'prune_rate': gyro_prune_rate
            },
            'mesh': {
                'nodes': len(self.mesh_adjacency),
                'avg_hops': mesh_avg_hops,
                'connectivity': mesh_connectivity
            },
            'comparison': {
                'hop_advantage': 'gyroid' if gyro_avg_hops < mesh_avg_hops else 'mesh',
                'hop_improvement_pct': abs(mesh_avg_hops - gyro_avg_hops) / max(mesh_avg_hops, 0.01) * 100
            }
        }


class CoherenceVerifier:
    def __init__(self, ternary_tolerance=0.05):
        self.ternary_tolerance = ternary_tolerance
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Initialize heads matching your EMS-3 architecture
        self.head_c = CarbonHead(input_dim=64, hidden_dim=128, output_dim=256).to(self.device)
        self.head_s = SiliconHead(input_dim=64, embed_dim=128, num_heads=4, num_layers=2, output_dim=256).to(self.device)
        self.head_f = FrequencyHead(input_dim=64, freq_bins=32, graph_nodes=16, output_dim=256).to(self.device)

    def calculate_phase_drift(self, z_c, z_s, z_f):
        """Measures cosine similarity distance to simulate phase drift between substrates."""
        drift_cs = 1.0 - F.cosine_similarity(z_c, z_s, dim=-1).mean().item()
        drift_sf = 1.0 - F.cosine_similarity(z_s, z_f, dim=-1).mean().item()
        drift_fc = 1.0 - F.cosine_similarity(z_f, z_c, dim=-1).mean().item()
        
        return drift_cs, drift_sf, drift_fc

    def run_closed_loop(self, duration_minutes=10, tick_rate=1.0, save_json=False):
        print(f"Initializing Tri-State Coherence Verification for {duration_minutes} minutes...")
        print(f"Target Ternary Tolerance: +/- {self.ternary_tolerance}")
        
        end_time = time.time() + (duration_minutes * 60)
        tick = 0
        
        # Log arrays for report generation
        drift_log = {'C-S': [], 'S-F': [], 'F-C': []}

        while time.time() < end_time:
            # Generate entropy-infused dummy packet
            x = torch.randn(1, 32, 64).to(self.device) 
            
            # Forward pass through all three intelligence substrates
            z_c = self.head_c(x)
            z_s = self.head_s(x)
            z_f = self.head_f(x)
            
            # Calculate drift
            d_cs, d_sf, d_fc = self.calculate_phase_drift(z_c, z_s, z_f)
            drift_log['C-S'].append(d_cs)
            drift_log['S-F'].append(d_sf)
            drift_log['F-C'].append(d_fc)
            
            # Check against ternary bounds (-1, 0, +1)
            max_drift = max(d_cs, d_sf, d_fc)
            status = "STABLE" if max_drift <= self.ternary_tolerance else "DRIFTING"
            
            if tick % 10 == 0 or duration_minutes < 1:
                print(f"[Tick {tick:04d}] Status: {status} | C-S: {d_cs:.4f} | S-F: {d_sf:.4f} | F-C: {d_fc:.4f}")
                
            time.sleep(tick_rate)
            tick += 1

        self.generate_report(drift_log, save_json=save_json)

    def generate_report(self, drift_log, save_json=False):
        print("\n=== COHERENCE VERIFICATION REPORT ===")
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "author": AUTHOR_METADATA["author"],
            "system": AUTHOR_METADATA["system"],
            "mesh": AUTHOR_METADATA["mesh"],
            "origin": AUTHOR_METADATA["origin"],
            "ternary_tolerance": self.ternary_tolerance,
            "links": {}
        }
        
        for pair, drifts in drift_log.items():
            avg_drift = np.mean(drifts)
            max_drift = np.max(drifts)
            print(f"Link {pair}: Avg Drift = {avg_drift:.4f} | Max Drift = {max_drift:.4f}")
            
            report_data["links"][pair] = {
                "avg_drift": float(avg_drift),
                "max_drift": float(max_drift),
                "breached": bool(max_drift > self.ternary_tolerance)
            }
            
            if max_drift > self.ternary_tolerance:
                print(f"  -> WARNING: {pair} connection breached ternary tolerance.")
        
        print("=====================================")
        
        if save_json:
            report_path = Path(__file__).parent / "coherence_report.json"
            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2)
            print(f"\n✓ Report saved to: {report_path}")
            print(f"  Author signature: {AUTHOR_METADATA['author']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tri-State Mesh Verification Stratum")
    parser.add_argument("--mode", choices=['coherence', 'nmo_stress', 'grounding', 'routing', 'check', 'gyroid_topology_test'], required=True)
    parser.add_argument("--duration", type=int, default=1, help="Test duration in minutes")
    parser.add_argument("--save-report", action="store_true", help="Save JSON report with author signature")
    parser.add_argument("--grid-size", type=int, default=8, help="Grid size for gyroid topology test")
    parser.add_argument("--ternary-threshold", type=float, default=0.3, help="Ternary threshold for gyroid node selection")
    
    args = parser.parse_args()
    
    if args.mode == 'coherence':
        verifier = CoherenceVerifier()
        verifier.run_closed_loop(duration_minutes=args.duration, save_json=args.save_report)
    elif args.mode == 'check':
        # Quick check mode - runs a single tick and generates signed report
        print("Running quick coherence check with author signature...")
        verifier = CoherenceVerifier()
        verifier.run_closed_loop(duration_minutes=0.1, save_json=True)
    elif args.mode == 'gyroid_topology_test':
        # Gyroid topology comparison test
        print(f"Running gyroid topology test (grid={args.grid_size}, threshold={args.ternary_threshold})...")
        verifier = GyroidTopologyVerifier(
            grid_size=args.grid_size,
            ternary_threshold=args.ternary_threshold
        )
        results = verifier.run_comparison(num_samples=200)
        
        # Optionally save results to JSON
        if args.save_report:
            report_path = Path(__file__).parent / "gyroid_topology_report.json"
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "author": AUTHOR_METADATA["author"],
                "system": AUTHOR_METADATA["system"],
                "mesh": AUTHOR_METADATA["mesh"],
                "origin": AUTHOR_METADATA["origin"],
                "test_type": "gyroid_topology_comparison",
                "parameters": {
                    "grid_size": args.grid_size,
                    "ternary_threshold": args.ternary_threshold
                },
                "results": results
            }
            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2, default=lambda x: float(x) if isinstance(x, np.floating) else str(x))
            print(f"\n✓ Gyroid topology report saved to: {report_path}")
    else:
        print(f"Mode '{args.mode}' scaffolded but not yet implemented. Run with --mode coherence or --mode gyroid_topology_test.")
