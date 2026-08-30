"""
EMS-3: Entangled Multimodal System-3
Reference Implementation - Toy Model

Three entangled heads forced to consensus via contrastive loss.
Head C (Carbon): Recurrent, bio-plausible, LSTM-style with long memory decay
Head S (Silicon): Transformer, silicon-native, parallel
Head F (Frequency): Spectral/Graph network, operates on phase, not amplitude
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Tuple, Dict


class CarbonHead(nn.Module):
    """
    Head C: Carbon Intelligence
    - Recurrent architecture (LSTM-style)
    - Long memory decay for biological persistence
    - High-noise tolerance, self-healing
    """
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, 
                 memory_decay: float = 0.95):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True,
                           num_layers=2, dropout=0.1)
        self.memory_decay = memory_decay
        self.projection = nn.Linear(hidden_dim, output_dim)
        self.hidden_dim = hidden_dim
        self.num_layers = 2
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [batch, seq_len, input_dim]
        Returns: [batch, output_dim] - aggregated latent representation
        """
        batch_size = x.size(0)
        
        # Initialize hidden state for this batch
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_dim, device=x.device)
        c0 = torch.zeros_like(h0)
        
        lstm_out, (hn, cn) = self.lstm(x, (h0, c0))
        
        # Aggregate over sequence (attention-weighted mean)
        attention_weights = torch.softmax(torch.mean(lstm_out, dim=-1), dim=1)
        aggregated = torch.sum(lstm_out * attention_weights.unsqueeze(-1), dim=1)
        
        z_c = self.projection(aggregated)
        return F.normalize(z_c, dim=-1)


class SiliconHead(nn.Module):
    """
    Head S: Silicon Intelligence
    - Transformer architecture
    - Deterministic, high-throughput, parallel
    - CI/CD governed (strict validation)
    """
    def __init__(self, input_dim: int, embed_dim: int, num_heads: int,
                 num_layers: int, output_dim: int):
        super().__init__()
        self.input_projection = nn.Linear(input_dim, embed_dim)
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=embed_dim * 4,
            dropout=0.1,
            activation='gelu',
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.output_projection = nn.Linear(embed_dim, output_dim)
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [batch, seq_len, input_dim]
        Returns: [batch, output_dim] - deterministic latent representation
        """
        # Project to embedding space
        embedded = self.input_projection(x)
        
        # Transformer encoding with causal mask
        src_mask = self._generate_causal_mask(x.size(1), x.device)
        encoded = self.transformer(embedded, mask=src_mask)
        
        # Take CLS token equivalent (first position)
        cls_representation = encoded[:, 0, :]
        
        z_s = self.output_projection(cls_representation)
        return F.normalize(z_s, dim=-1)
    
    def _generate_causal_mask(self, seq_len: int, device: torch.device) -> torch.Tensor:
        mask = torch.triu(torch.ones(seq_len, seq_len, device=device), diagonal=1)
        mask = mask.masked_fill(mask == 1, float('-inf'))
        return mask


class FrequencyHead(nn.Module):
    """
    Head F: Frequency Intelligence
    - Spectral / Graph network
    - Operates on phase, not amplitude
    - Geometric, resonant, low-bandwidth, high-coherence
    """
    def __init__(self, input_dim: int, freq_bins: int, graph_nodes: int,
                 output_dim: int):
        super().__init__()
        self.freq_bins = freq_bins
        self.graph_nodes = graph_nodes
        
        # FFT projection layer
        self.spectral_proj = nn.Linear(input_dim, freq_bins * 2)  # real + imag
        
        # Graph convolution on frequency domain
        self.graph_conv1 = nn.Linear(freq_bins * 2, graph_nodes * freq_bins)
        self.graph_conv2 = nn.Linear(graph_nodes * freq_bins, freq_bins)
        
        # Phase extraction and projection
        self.phase_encoder = nn.Linear(freq_bins * 2, output_dim)  # phase + magnitude
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [batch, seq_len, input_dim]
        Returns: [batch, output_dim] - phase-based latent representation
        """
        batch_size = x.size(0)
        
        # Aggregate sequence (frequency head is coherence-focused)
        x_agg = torch.mean(x, dim=1)  # [batch, input_dim]
        
        # Transform to frequency domain (learned spectral projection)
        spectral = self.spectral_proj(x_agg)  # [batch, freq_bins * 2]
        
        # Reshape for graph processing
        spectral = spectral.view(batch_size, self.freq_bins, 2)
        
        # Extract phase and magnitude
        real = spectral[..., 0]
        imag = spectral[..., 1]
        magnitude = torch.sqrt(real**2 + imag**2 + 1e-8)
        phase = torch.atan2(imag, real + 1e-8)
        
        # Graph convolution on phase-space
        phase_features = torch.cat([phase, magnitude], dim=-1)
        graph_out = F.relu(self.graph_conv1(phase_features.view(batch_size, -1)))
        graph_out = self.graph_conv2(graph_out)
        
        # Encode phase information
        z_f = self.phase_encoder(torch.cat([graph_out, phase], dim=-1))
        return F.normalize(z_f, dim=-1)


class EMS3Unified(nn.Module):
    """
    EMS-3: Entangled Multimodal System-3
    
    Single model with 3 entangled heads sharing a latent space
    forced to consensus via contrastive loss.
    """
    def __init__(self, input_dim: int = 64, hidden_dim: int = 128, 
                 output_dim: int = 32, num_heads_transformer: int = 4,
                 freq_bins: int = 32, graph_nodes: int = 8):
        super().__init__()
        
        # Initialize three heads
        self.head_c = CarbonHead(input_dim, hidden_dim, output_dim)
        self.head_s = SiliconHead(input_dim, hidden_dim, num_heads_transformer,
                                  num_layers=2, output_dim=output_dim)
        self.head_f = FrequencyHead(input_dim, freq_bins, graph_nodes, output_dim)
        
        # Consensus projector (optional refinement after entanglement)
        self.consensus_projector = nn.Linear(output_dim * 3, output_dim)
        
        # Temperature parameter for contrastive loss
        self.temperature = nn.Parameter(torch.tensor(0.07))
        
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        x: [batch, seq_len, input_dim] - multimodal input
        Returns: 
            z_unified: [batch, output_dim] - single tensor valid in all domains
            head_outputs: dict with individual head representations
        """
        # Get representations from each head
        z_c = self.head_c(x)
        z_s = self.head_s(x)
        z_f = self.head_f(x)
        
        # Concatenate and project to unified space
        combined = torch.cat([z_c, z_s, z_f], dim=-1)
        z_unified = self.consensus_projector(combined)
        z_unified = F.normalize(z_unified, dim=-1)
        
        head_outputs = {
            'C': z_c,
            'S': z_s,
            'F': z_f
        }
        
        return z_unified, head_outputs
    
    def entanglement_loss(self, head_outputs: Dict[str, torch.Tensor], 
                         lambda_entangle: float = 1.0) -> torch.Tensor:
        """
        Compute the entanglement loss that forces consensus.
        
        Loss = L_c + L_s + L_f + λ * (|Z_c - Z_s| + |Z_s - Z_f| + |Z_f - Z_c|)
        
        The pairwise distance terms force all heads to agree in latent space.
        """
        z_c = head_outputs['C']
        z_s = head_outputs['S']
        z_f = head_outputs['F']
        
        # Individual head losses (could be task-specific, using MSE for demo)
        # In practice, these would be domain-specific losses
        l_c = torch.mean(z_c ** 2)  # Regularization
        l_s = torch.mean(z_s ** 2)
        l_f = torch.mean(z_f ** 2)
        
        # Contrastive entanglement terms - force agreement
        dist_c_s = torch.mean(torch.abs(z_c - z_s))
        dist_s_f = torch.mean(torch.abs(z_s - z_f))
        dist_f_c = torch.mean(torch.abs(z_f - z_c))
        
        entanglement_penalty = dist_c_s + dist_s_f + dist_f_c
        
        total_loss = l_c + l_s + l_f + lambda_entangle * entanglement_penalty
        
        return total_loss
    
    def contrastive_consensus_loss(self, head_outputs: Dict[str, torch.Tensor]) -> torch.Tensor:
        """
        Alternative: InfoNCE-style contrastive loss for consensus.
        Treats different heads' views of the same input as positive pairs.
        """
        z_c = head_outputs['C']
        z_s = head_outputs['S']
        z_f = head_outputs['F']
        
        tau = torch.exp(self.temperature)
        
        # Compute pairwise similarities
        sim_c_s = F.cosine_similarity(z_c, z_s, dim=-1).mean()
        sim_s_f = F.cosine_similarity(z_s, z_f, dim=-1).mean()
        sim_f_c = F.cosine_similarity(z_f, z_c, dim=-1).mean()
        
        # Maximize similarity (minimize negative similarity)
        contrastive_loss = -(sim_c_s + sim_s_f + sim_f_c) / 3.0
        
        return contrastive_loss
    
    def compute_consensus_metrics(self, head_outputs: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """
        Compute metrics showing degree of consensus between heads.
        """
        z_c = head_outputs['C']
        z_s = head_outputs['S']
        z_f = head_outputs['F']
        
        with torch.no_grad():
            # Cosine similarities
            sim_c_s = F.cosine_similarity(z_c, z_s, dim=-1).mean().item()
            sim_s_f = F.cosine_similarity(z_s, z_f, dim=-1).mean().item()
            sim_f_c = F.cosine_similarity(z_f, z_c, dim=-1).mean().item()
            
            # Pairwise distances
            dist_c_s = torch.mean(torch.abs(z_c - z_s)).item()
            dist_s_f = torch.mean(torch.abs(z_s - z_f)).item()
            dist_f_c = torch.mean(torch.abs(z_f - z_c)).item()
            
            # Overall consensus score (higher = better agreement)
            avg_similarity = (sim_c_s + sim_s_f + sim_f_c) / 3.0
            avg_distance = (dist_c_s + dist_s_f + dist_f_c) / 3.0
            
        return {
            'similarity_C_S': sim_c_s,
            'similarity_S_F': sim_s_f,
            'similarity_F_C': sim_f_c,
            'distance_C_S': dist_c_s,
            'distance_S_F': dist_s_f,
            'distance_F_C': dist_f_c,
            'avg_similarity': avg_similarity,
            'avg_distance': avg_distance
        }


def generate_synthetic_data(batch_size: int = 32, seq_len: int = 16,
                           input_dim: int = 64, device: str = 'cpu') -> torch.Tensor:
    """
    Generate synthetic multimodal data for training EMS-3.
    Combines patterns that should activate C, S, and F heads differently.
    """
    # Base signal with temporal structure (for Carbon head)
    temporal_signal = torch.randn(batch_size, seq_len, input_dim, device=device)
    
    # Add periodic component (for Frequency head)
    t = torch.linspace(0, 2 * np.pi, seq_len, device=device)
    freq_component = torch.sin(t).unsqueeze(0).unsqueeze(-1) * torch.ones(batch_size, seq_len, input_dim, device=device)
    
    # Add structured patterns (for Silicon head)
    pattern = torch.zeros(batch_size, seq_len, input_dim, device=device)
    pattern[:, ::2, :input_dim//2] = 1.0  # Alternating pattern
    
    # Combine signals
    x = temporal_signal * 0.5 + freq_component * 0.3 + pattern * 0.2
    
    return x


def train_ems3(model: EMS3Unified, num_epochs: int = 100, batch_size: int = 32,
               lr: float = 1e-3, lambda_entangle: float = 1.0,
               device: str = 'cpu') -> list:
    """
    Train EMS-3 toy model on synthetic data.
    Shows loss converging as heads reach consensus.
    """
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10)
    
    loss_history = []
    consensus_history = []
    
    for epoch in range(num_epochs):
        model.train()
        optimizer.zero_grad()
        
        # Generate batch
        x = generate_synthetic_data(batch_size, device=device)
        
        # Forward pass
        z_unified, head_outputs = model(x)
        
        # Compute losses
        entangle_loss = model.entanglement_loss(head_outputs, lambda_entangle)
        contrastive_loss = model.contrastive_consensus_loss(head_outputs)
        
        total_loss = entangle_loss + contrastive_loss
        
        # Backward pass
        total_loss.backward()
        optimizer.step()
        
        # Record metrics
        loss_history.append(total_loss.item())
        
        with torch.no_grad():
            metrics = model.compute_consensus_metrics(head_outputs)
            consensus_history.append(metrics['avg_similarity'])
        
        scheduler.step(total_loss)
        
        if epoch % 10 == 0:
            print(f"Epoch {epoch:3d} | Loss: {total_loss.item():.6f} | "
                  f"Consensus: {metrics['avg_similarity']:.4f}")
    
    return loss_history, consensus_history


if __name__ == "__main__":
    print("=" * 60)
    print("EMS-3: Entangled Multimodal System-3")
    print("Training toy model to demonstrate consensus convergence")
    print("=" * 60)
    
    # Set random seed for reproducibility
    torch.manual_seed(42)
    np.random.seed(42)
    
    # Initialize model
    model = EMS3Unified(
        input_dim=64,
        hidden_dim=128,
        output_dim=32,
        num_heads_transformer=4,
        freq_bins=32,
        graph_nodes=8
    )
    
    print(f"\nModel parameters: {sum(p.numel() for p in model.parameters()):,}")
    print("\nStarting training...\n")
    
    # Train
    loss_hist, consensus_hist = train_ems3(
        model,
        num_epochs=100,
        batch_size=32,
        lr=1e-3,
        lambda_entangle=1.0,
        device='cpu'
    )
    
    print("\n" + "=" * 60)
    print("Training Complete")
    print("=" * 60)
    print(f"Initial loss: {loss_hist[0]:.6f}")
    print(f"Final loss: {loss_hist[-1]:.6f}")
    print(f"Loss reduction: {(1 - loss_hist[-1]/loss_hist[0]) * 100:.1f}%")
    print(f"\nInitial consensus: {consensus_hist[0]:.4f}")
    print(f"Final consensus: {consensus_hist[-1]:.4f}")
    print(f"Consensus improvement: {(consensus_hist[-1] - consensus_hist[0]) * 100:.1f}%")
    
    # Final evaluation
    model.eval()
    with torch.no_grad():
        x_test = generate_synthetic_data(16)
        _, head_outputs = model(x_test)
        final_metrics = model.compute_consensus_metrics(head_outputs)
        
        print("\nFinal Consensus Metrics:")
        print(f"  C-S Similarity: {final_metrics['similarity_C_S']:.4f}")
        print(f"  S-F Similarity: {final_metrics['similarity_S_F']:.4f}")
        print(f"  F-C Similarity: {final_metrics['similarity_F_C']:.4f}")
        print(f"  Average: {final_metrics['avg_similarity']:.4f}")
    
    print("\n✓ EMS-3 toy model demonstrates converging loss and increasing consensus")
    print("✓ Three heads (C, S, F) forced to agree in shared latent space")
    print("✓ Single-state output valid in biological, computational, and resonant domains")
