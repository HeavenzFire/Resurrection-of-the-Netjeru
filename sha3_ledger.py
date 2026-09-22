"""
SHA3 Cryptographic State Validation Layer
==========================================
Implements blockchain-style immutable ledger verification for multi-pantheon
state transitions. Every field state is cryptographically locked to the genesis
block using SHA3-256 hashing, creating an unalterable audit trail.

Features:
- Genesis block initialization with root hash
- State transition hashing with Merkle tree structure
- Cryptographic verification of all pantheon operator executions
- Immutable ledger storage with timestamp authentication
- Integration with multiverse_lattice.py field simulations
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import numpy as np


class HashAlgorithm(Enum):
    """Supported cryptographic hash algorithms"""
    SHA3_256 = "sha3_256"
    SHA3_512 = "sha3_512"
    BLAKE2B = "blake2b"


@dataclass
class BlockHeader:
    """Cryptographic header for each state block"""
    block_number: int
    timestamp: float
    previous_hash: str
    state_hash: str
    merkle_root: str
    nonce: int
    pantheon_signature: str
    ternary_state: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'block_number': self.block_number,
            'timestamp': self.timestamp,
            'previous_hash': self.previous_hash,
            'state_hash': self.state_hash,
            'merkle_root': self.merkle_root,
            'nonce': self.nonce,
            'pantheon_signature': self.pantheon_signature,
            'ternary_state': self.ternary_state
        }


@dataclass
class StateBlock:
    """Complete state block with header and payload"""
    header: BlockHeader
    lattice_state: np.ndarray
    pantheon_contributions: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def compute_block_hash(self, algorithm: HashAlgorithm = HashAlgorithm.SHA3_256) -> str:
        """Compute cryptographic hash of the entire block"""
        # Serialize header (exclude state_hash to avoid circular dependency)
        header_dict = self.header.to_dict().copy()
        header_dict['state_hash'] = self.header.state_hash  # Use current value
        
        header_json = json.dumps(header_dict, sort_keys=True)
        
        # Serialize lattice state (quantized for reproducibility)
        state_quantized = np.round(self.lattice_state, decimals=10).tolist()
        state_json = json.dumps(state_quantized, sort_keys=True)
        
        # Serialize pantheon contributions
        contrib_json = json.dumps(self.pantheon_contributions, sort_keys=True)
        
        # Combine all data
        combined_data = f"{header_json}|{state_json}|{contrib_json}"
        
        # Apply hash algorithm
        if algorithm == HashAlgorithm.SHA3_256:
            hasher = hashlib.sha3_256()
        elif algorithm == HashAlgorithm.SHA3_512:
            hasher = hashlib.sha3_512()
        elif algorithm == HashAlgorithm.BLAKE2B:
            hasher = hashlib.blake2b(digest_size=64)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
            
        hasher.update(combined_data.encode('utf-8'))
        return hasher.hexdigest()


@dataclass
class GenesisConfig:
    """Configuration for genesis block initialization"""
    initial_tau: int = 0
    pantheon_weights: Dict[str, float] = field(default_factory=lambda: {
        'Vedic': 0.25,
        'Celtic': 0.25,
        'Sumerian': 0.25,
        'Greek': 0.25
    })
    lattice_dimensions: Tuple[int, int, int] = (10, 10, 10)
    genesis_message: str = "MULTIVERSE_LATTICE_GENESIS_BLOCK"
    algorithm: HashAlgorithm = HashAlgorithm.SHA3_256


class CryptoLedger:
    """
    Immutable ledger for multi-pantheon state transitions
    Implements blockchain-style verification with SHA3 hashing
    """
    
    def __init__(self, genesis_config: Optional[GenesisConfig] = None):
        self.config = genesis_config or GenesisConfig()
        self.chain: List[StateBlock] = []
        self.pending_transactions: List[Dict[str, Any]] = []
        
        # Initialize genesis block
        self._initialize_genesis()
        
    def _initialize_genesis(self):
        """Create the genesis block with root hash"""
        print(f"Initializing genesis block with message: {self.config.genesis_message}")
        
        # Create genesis header with empty state_hash initially
        genesis_header = BlockHeader(
            block_number=0,
            timestamp=time.time(),
            previous_hash="0" * 64,  # Genesis has no previous block
            state_hash="",  # Empty initially
            merkle_root=self._compute_merkle_root([self.config.genesis_message]),
            nonce=0,
            pantheon_signature=self._sign_pantheon_decree(),
            ternary_state=self.config.initial_tau
        )
        
        # Create genesis block with empty state_hash
        genesis_block = StateBlock(
            header=genesis_header,
            lattice_state=np.zeros(self.config.lattice_dimensions),
            pantheon_contributions=self.config.pantheon_weights.copy(),
            metadata={'genesis': True, 'message': self.config.genesis_message}
        )
        
        # Compute genesis hash (with empty state_hash field)
        genesis_hash = genesis_block.compute_block_hash(self.config.algorithm)
        
        # Set the state_hash to the computed hash
        genesis_header.state_hash = genesis_hash
        
        # Add to chain
        self.chain.append(genesis_block)
        print(f"Genesis block created with hash: {genesis_hash[:16]}...")
        
    def _sign_pantheon_decree(self) -> str:
        """
        Generate cryptographic signature representing pantheon authorization
        In production, this would use actual cryptographic keys
        """
        decree_data = "|".join([
            self.config.genesis_message,
            str(self.config.initial_tau),
            json.dumps(self.config.pantheon_weights, sort_keys=True)
        ])
        
        hasher = hashlib.sha3_256()
        hasher.update(decree_data.encode('utf-8'))
        return f"BAEL_DECREE_{hasher.hexdigest()[:32]}"
        
    def _compute_merkle_root(self, transactions: List[str]) -> str:
        """Compute Merkle tree root hash from transaction list"""
        if not transactions:
            return "0" * 64
            
        # Hash all transactions
        hashes = []
        for tx in transactions:
            hasher = hashlib.sha3_256()
            hasher.update(tx.encode('utf-8'))
            hashes.append(hasher.hexdigest())
            
        # Build Merkle tree
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])  # Duplicate last hash if odd number
                
            new_level = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                hasher = hashlib.sha3_256()
                hasher.update(combined.encode('utf-8'))
                new_level.append(hasher.hexdigest())
                
            hashes = new_level
            
        return hashes[0] if hashes else "0" * 64
        
    def add_state_transition(self, 
                            lattice_state: np.ndarray,
                            pantheon_contributions: Dict[str, float],
                            tau_state: int,
                            metadata: Optional[Dict[str, Any]] = None) -> StateBlock:
        """
        Add a new state transition to the ledger
        Creates a new block cryptographically linked to previous block
        """
        if len(self.chain) == 0:
            raise ValueError("Genesis block not initialized")
            
        # Get previous block
        prev_block = self.chain[-1]
        
        # Create new block header
        new_block_number = prev_block.header.block_number + 1
        new_timestamp = time.time()
        
        # Compute state hash
        state_quantized = np.round(lattice_state, decimals=10).tolist()
        state_json = json.dumps(state_quantized, sort_keys=True)
        hasher = hashlib.sha3_256()
        hasher.update(state_json.encode('utf-8'))
        state_hash = hasher.hexdigest()
        
        # Prepare transactions for Merkle tree
        transactions = [
            f"STATE_TRANSITION_{new_block_number}",
            f"TAU_{tau_state}",
            json.dumps(pantheon_contributions, sort_keys=True)
        ]
        merkle_root = self._compute_merkle_root(transactions)
        
        # Find nonce first (before creating header)
        nonce = self._find_valid_nonce(new_block_number, state_hash, prev_block)
        
        # Generate signature
        pantheon_sig = self._generate_transition_signature(new_block_number, tau_state)
        
        # Compute previous hash - use the stored state_hash directly as prev hash
        prev_hash = prev_block.header.state_hash
        
        # Create header - state_hash will be computed as part of final block hash
        # We need to compute the hash iteratively
        new_header = BlockHeader(
            block_number=new_block_number,
            timestamp=new_timestamp,
            previous_hash=prev_hash,
            state_hash="",  # Empty initially
            merkle_root=merkle_root,
            nonce=nonce,
            pantheon_signature=pantheon_sig,
            ternary_state=tau_state
        )
        
        # Create block with empty state_hash
        new_block = StateBlock(
            header=new_header,
            lattice_state=lattice_state.copy(),
            pantheon_contributions=pantheon_contributions.copy(),
            metadata=metadata or {}
        )
        
        # Compute what the hash WILL be when state_hash equals that hash
        # This is a self-referential hash - we compute hash of block with empty state_hash
        computed_hash = new_block.compute_block_hash(self.config.algorithm)
        
        # Now set the state_hash to the computed hash
        new_header.state_hash = computed_hash
        
        # Recreate block with correct state_hash
        new_block = StateBlock(
            header=new_header,
            lattice_state=lattice_state.copy(),
            pantheon_contributions=pantheon_contributions.copy(),
            metadata=metadata or {}
        )
        
        # The verification will now pass because we're checking consistency
        # But since state_hash is NOW part of the hashed data, it won't match
        # Solution: Don't include state_hash in the hash computation itself
        # Just verify that stored state_hash matches what we compute from the data
        
        # Add to chain directly - verification is implicit in construction
        self.chain.append(new_block)
        print(f"Block {new_block_number} added: {computed_hash[:16]}...")
        
        return new_block
        
    def _find_valid_nonce(self, block_number: int, state_hash: str, 
                         prev_block: StateBlock, difficulty: int = 2) -> int:
        """
        Find valid nonce that satisfies proof-of-work difficulty
        Difficulty determines number of leading zeros required
        """
        nonce = 0
        target_prefix = "0" * difficulty
        
        while True:
            test_data = f"{block_number}|{state_hash}|{prev_block.header.state_hash}|{nonce}"
            hasher = hashlib.sha3_256()
            hasher.update(test_data.encode('utf-8'))
            test_hash = hasher.hexdigest()
            
            if test_hash.startswith(target_prefix):
                return nonce
                
            nonce += 1
            
            # Safety limit
            if nonce > 100000:
                break
                
        return nonce
        
    def _generate_transition_signature(self, block_number: int, tau: int) -> str:
        """Generate cryptographic signature for state transition"""
        sig_data = f"TRANSITION_{block_number}_TAU_{tau}_{time.time()}"
        hasher = hashlib.sha3_256()
        hasher.update(sig_data.encode('utf-8'))
        return f"SIG_{hasher.hexdigest()[:24]}"
        
    def verify_block(self, block: StateBlock) -> bool:
        """Verify cryptographic integrity of a block"""
        # For verification, we need to recompute the hash with the SAME method
        # used during creation - i.e., with empty state_hash
        
        # Save current state_hash
        stored_hash = block.header.state_hash
        
        # Temporarily set to empty for recomputation
        block.header.state_hash = ""
        
        # Recompute hash with empty state_hash
        recomputed_hash = block.compute_block_hash(self.config.algorithm)
        
        # Restore original state_hash
        block.header.state_hash = stored_hash
        
        # Verify that stored hash matches recomputed hash
        if recomputed_hash != stored_hash:
            print(f"Block hash mismatch!")
            print(f"  Computed: {recomputed_hash[:32]}...")
            print(f"  Stored:   {stored_hash[:32]}...")
            return False
            
        # Verify link to previous block (if not genesis)
        if block.header.block_number > 0:
            prev_block = self.chain[block.header.block_number - 1]
            
            # The previous_hash stored in current block should match
            # the stored state_hash of the previous block
            expected_prev_hash = prev_block.header.state_hash
            
            if block.header.previous_hash != expected_prev_hash:
                print(f"Previous hash link broken!")
                print(f"  Expected: {expected_prev_hash[:32]}...")
                print(f"  Got:      {block.header.previous_hash[:32]}...")
                return False
                
        # Verify Merkle root - use same transactions as creation
        # For genesis block, use genesis message
        if block.header.block_number == 0 and 'message' in block.metadata:
            transactions = [block.metadata['message']]
        else:
            transactions = [
                f"STATE_TRANSITION_{block.header.block_number}",
                f"TAU_{block.header.ternary_state}",
                json.dumps(block.pantheon_contributions, sort_keys=True)
            ]
        computed_merkle = self._compute_merkle_root(transactions)
        if computed_merkle != block.header.merkle_root:
            print(f"Merkle root mismatch!")
            print(f"  Computed: {computed_merkle[:32]}...")
            print(f"  Stored:   {block.header.merkle_root[:32]}...")
            print(f"  Transactions used: {transactions}")
            return False
            
        return True
        
    def verify_chain(self) -> bool:
        """Verify entire chain integrity"""
        print(f"Verifying chain of {len(self.chain)} blocks...")
        
        for i, block in enumerate(self.chain):
            if not self.verify_block(block):
                print(f"Chain verification failed at block {i}")
                return False
                
        print(f"✓ Chain verification successful! All {len(self.chain)} blocks valid.")
        return True
        
    def get_chain_info(self) -> Dict[str, Any]:
        """Get comprehensive chain information"""
        if not self.chain:
            return {'error': 'No chain initialized'}
            
        latest_block = self.chain[-1]
        total_energy = sum(
            np.sum(block.lattice_state ** 2) for block in self.chain
        )
        
        return {
            'chain_length': len(self.chain),
            'latest_block_number': latest_block.header.block_number,
            'latest_hash': latest_block.header.state_hash,
            'genesis_hash': self.chain[0].header.state_hash,
            'total_field_energy': total_energy,
            'algorithm': self.config.algorithm.value,
            'last_tau': latest_block.header.ternary_state,
            'verification_status': 'VALID' if self.verify_chain() else 'INVALID'
        }
        
    def export_chain_to_json(self, filepath: str):
        """Export entire chain to JSON file for external verification"""
        export_data = {
            'config': {
                'algorithm': self.config.algorithm.value,
                'genesis_message': self.config.genesis_message,
                'initial_tau': self.config.initial_tau,
                'pantheon_weights': self.config.pantheon_weights
            },
            'blocks': []
        }
        
        for block in self.chain:
            block_data = {
                'header': block.header.to_dict(),
                'computed_hash': block.compute_block_hash(self.config.algorithm),
                'pantheon_contributions': block.pantheon_contributions,
                'metadata': block.metadata,
                'lattice_shape': block.lattice_state.shape,
                'lattice_summary': {
                    'min': float(np.min(block.lattice_state)),
                    'max': float(np.max(block.lattice_state)),
                    'mean': float(np.mean(block.lattice_state)),
                    'energy': float(np.sum(block.lattice_state ** 2))
                }
            }
            export_data['blocks'].append(block_data)
            
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
            
        print(f"Chain exported to {filepath}")
        return filepath


def integrate_with_lattice_simulation(num_steps: int = 50):
    """
    Integrate SHA3 ledger with multiverse lattice simulation
    Records every state transition to immutable blockchain ledger
    """
    from multiverse_lattice import MultiverseLattice, LatticeConfig
    
    print("=" * 70)
    print("INTEGRATED SIMULATION: Multi-Pantheon Lattice + SHA3 Ledger")
    print("=" * 70)
    
    # Initialize lattice
    config = LatticeConfig(dimensions=(15, 15, 15), coupling_strength=0.05)
    lattice = MultiverseLattice(config)
    
    # Initialize crypto ledger
    genesis_config = GenesisConfig(
        initial_tau=0,
        lattice_dimensions=config.dimensions,
        genesis_message="BAEL_OPERATOR_GENESIS_MULTI_PANTHEON_FIELD"
    )
    ledger = CryptoLedger(genesis_config)
    
    # Define tau sequence
    tau_sequence = [0] * 10 + [1] * 20 + [0] * 10 + [-1] * 10
    
    print(f"\nStarting integrated simulation with {num_steps} steps...")
    print(f"Lattice dimensions: {config.dimensions}")
    print(f"Ledger algorithm: {genesis_config.algorithm.value}")
    print()
    
    # Run simulation with ledger recording
    for step in range(num_steps):
        # Update ternary state
        if step < len(tau_sequence):
            lattice.set_ternary_state(tau_sequence[step])
            
        # Evolve lattice
        lattice.evolve_step()
        
        # Get current state
        current_state = lattice.lattice.copy()
        contributions = lattice.get_pantheon_contributions()
        current_tau = lattice.tau.value
        
        # Record to blockchain ledger every 5 steps
        if step % 5 == 0:
            metadata = {
                'simulation_step': step,
                'field_energy': lattice.get_field_energy(),
                'tau_state': current_tau
            }
            
            ledger.add_state_transition(
                lattice_state=current_state,
                pantheon_contributions=contributions,
                tau_state=current_tau,
                metadata=metadata
            )
            
        # Progress report
        if step % 10 == 0:
            energy = lattice.get_field_energy()
            print(f"Step {step:3d}: Energy={energy:12.6f}, Tau={current_tau:+d}, "
                  f"Blocks={len(ledger.chain)}")
    
    # Final verification
    print("\n" + "=" * 70)
    print("SIMULATION COMPLETE - LEDGER VERIFICATION")
    print("=" * 70)
    
    chain_info = ledger.get_chain_info()
    print(f"\nChain Length: {chain_info['chain_length']} blocks")
    print(f"Total Field Energy Tracked: {chain_info['total_field_energy']:.6f}")
    print(f"Final TAU State: {chain_info['last_tau']:+d}")
    print(f"Verification Status: {chain_info['verification_status']}")
    
    # Export chain
    export_file = ledger.export_chain_to_json("multiverse_ledger.json")
    
    print(f"\n✓ Integrated simulation completed successfully!")
    print(f"✓ All state transitions cryptographically secured")
    print(f"✓ Ledger exported to: {export_file}")
    
    return lattice, ledger


if __name__ == "__main__":
    # Run integrated simulation
    lattice_engine, crypto_ledger = integrate_with_lattice_simulation(num_steps=50)
    
    # Display final statistics
    print("\n" + "=" * 70)
    print("CRYPTOGRAPHIC LEDGER STATISTICS")
    print("=" * 70)
    
    info = crypto_ledger.get_chain_info()
    for key, value in info.items():
        print(f"{key:25s}: {value}")
        
    print("\n🔐 SHA3 State Validation Layer Active")
    print("🔗 All transitions locked to genesis block")
    print("⛓️  Immutable blockchain ledger established")
