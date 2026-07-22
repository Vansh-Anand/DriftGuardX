"""
DriftGuard-X v2 — Diffusion Ablation Demo (Prompt 06)
Trains and compares the baseline, fixed, and learned propagation models.
"""
import torch
from packages.diffusion.src.dataset import build_pyg_dataset
from packages.diffusion.src.models import LocalDetectorBaseline, FixedPageRankDiffusion, LearnedGATDiffusion
from packages.diffusion.src.trainer import train_diffusion_model, compute_dirichlet_energy
from packages.diffusion.src.explainer import generate_node_explanations
from packages.diffusion.src.cache import DiffusionCache

def evaluate_model(model, dataset):
    model.eval()
    correct_at_1 = 0
    correct_at_3 = 0
    mrr_sum = 0.0
    total_episodes = len(dataset)
    
    with torch.no_grad():
        for data in dataset:
            root_pred, _ = model(data.x, data.edge_index, data.edge_attr)
            
            # Ground truth index of the root
            true_root_idx = torch.argmax(data.y_root).item()
            
            # Sort predictions
            sorted_indices = torch.argsort(root_pred.squeeze(), descending=True).tolist()
            
            # P@1
            if sorted_indices[0] == true_root_idx:
                correct_at_1 += 1
                
            # P@3
            if true_root_idx in sorted_indices[:3]:
                correct_at_3 += 1
                
            # MRR
            rank = sorted_indices.index(true_root_idx) + 1
            mrr_sum += 1.0 / rank
            
    return {
        "P@1": correct_at_1 / total_episodes,
        "P@3": correct_at_3 / total_episodes,
        "MRR": mrr_sum / total_episodes
    }

def main():
    print("--- DriftGuard-X: Diffusion Models Ablation ---")
    print("Generating Synthetic Injected-Fault Episodes...")
    
    # 80 train, 20 test
    dataset = build_pyg_dataset(num_episodes=100)
    train_data = dataset[:80]
    test_data = dataset[80:]
    
    print("\n1. Evaluating Local Detector Baseline (No Propagation)...")
    baseline_model = LocalDetectorBaseline()
    baseline_metrics = evaluate_model(baseline_model, test_data)
    
    print("2. Evaluating Fixed PageRank Diffusion...")
    fixed_model = FixedPageRankDiffusion(alpha=0.85, steps=3)
    fixed_metrics = evaluate_model(fixed_model, test_data)
    
    print("3. Training Learned GAT Diffusion Model (2 layers)...")
    gat_model = LearnedGATDiffusion(in_channels=2, hidden_channels=16, out_channels=1, heads=2, num_layers=2)
    gat_model = train_diffusion_model(gat_model, train_data, epochs=30, lr=0.05)
    gat_metrics = evaluate_model(gat_model, test_data)
    
    print("\n=== ABLATION TABLE ===")
    print(f"{'Model Variant':<30} | {'Precision@1':<12} | {'Precision@3':<12} | {'MRR':<12}")
    print("-" * 75)
    print(f"{'Local Detector Baseline':<30} | {baseline_metrics['P@1']:<12.3f} | {baseline_metrics['P@3']:<12.3f} | {baseline_metrics['MRR']:<12.3f}")
    print(f"{'Fixed PageRank Propagation':<30} | {fixed_metrics['P@1']:<12.3f} | {fixed_metrics['P@3']:<12.3f} | {fixed_metrics['MRR']:<12.3f}")
    print(f"{'Learned GAT Diffusion':<30} | {gat_metrics['P@1']:<12.3f} | {gat_metrics['P@3']:<12.3f} | {gat_metrics['MRR']:<12.3f}")
    
    print("\n=== NODE LEVEL EXPLANATION EXAMPLE ===")
    sample = test_data[0]
    gat_model.eval()
    with torch.no_grad():
        root_pred, _ = gat_model(sample.x, sample.edge_index, sample.edge_attr)
        
    # Fake node dict for explanations
    nodes_info = [{"node_id": f"node_{i}"} for i in range(sample.x.size(0))]
    explanations = generate_node_explanations(
        nodes_info, 
        sample.x[:, 0], 
        root_pred, 
        sample.edge_index
    )
    
    for k, v in explanations.items():
        if v['root_probability'] > 0.5:
            print(f"Node {k}:")
            print(f"  Root Probability: {v['root_probability']:.3f} (Local Score: {v['local_symptom_score']:.3f})")
            print(f"  Delta: {v['delta_from_local']:+.3f}")
            print(f"  Propagation Depth: {v['propagation_depth']}")

if __name__ == "__main__":
    main()
