"""
DriftGuard-X v2 — Diffusion Model Trainer & Diagnostics
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

class DiffusionLoss(nn.Module):
    def __init__(self, lambda_symptom=0.5, lambda_sparse=0.01, lambda_contrastive=0.1):
        super().__init__()
        self.lambda_symptom = lambda_symptom
        self.lambda_sparse = lambda_sparse
        self.lambda_contrastive = lambda_contrastive
        self.bce = nn.BCELoss()

    def forward(self, root_pred, symptom_pred, root_true, symptom_true, model=None):
        # 1. Root Classification Loss
        loss_root = self.bce(root_pred, root_true)
        
        # 2. Symptom Propagation Consistency (MSE)
        loss_symptom = F.mse_loss(symptom_pred, symptom_true)
        
        # 3. Sparsity / Interpretability (L1 on attention weights if accessible)
        # For simplicity in this demo, we apply L1 to the root_pred to encourage sparse roots
        loss_sparse = torch.mean(torch.abs(root_pred))
        
        # 4. Contrastive Separation (Root vs Propagated)
        # Push root predictions and symptom predictions apart where root is false but symptom is true
        contrastive_mask = (root_true == 0.0) & (symptom_true == 1.0)
        if contrastive_mask.any():
            loss_contrast = torch.mean(torch.clamp(root_pred[contrastive_mask] - symptom_pred[contrastive_mask] + 0.5, min=0.0))
        else:
            loss_contrast = 0.0
            
        total_loss = loss_root + self.lambda_symptom * loss_symptom + self.lambda_sparse * loss_sparse + self.lambda_contrastive * loss_contrast
        
        return total_loss, {
            "root_loss": loss_root.item(),
            "symptom_loss": loss_symptom.item(),
            "sparse_loss": loss_sparse.item(),
            "contrast_loss": loss_contrast.item() if isinstance(loss_contrast, torch.Tensor) else loss_contrast
        }

def compute_dirichlet_energy(x, edge_index):
    """
    Diagnostic for oversmoothing: lower energy means more smoothing.
    """
    if edge_index.size(1) == 0:
        return 0.0
    src = edge_index[0]
    dst = edge_index[1]
    energy = torch.norm(x[src] - x[dst], p=2, dim=1).pow(2).mean().item()
    return energy

def train_diffusion_model(model, dataset, epochs=50, lr=0.01):
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = DiffusionLoss()
    
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for data in dataset:
            optimizer.zero_grad()
            root_pred, symptom_pred = model(data.x, data.edge_index, data.edge_attr)
            
            loss, metrics = criterion(root_pred, symptom_pred, data.y_root, data.y_symptom)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
    return model
