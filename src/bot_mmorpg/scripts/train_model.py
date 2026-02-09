"""
BOT-MMORPG-AI Training Script (PyTorch)

Train neural network models on recorded gameplay data.
Supports multiple architectures with modern training practices.

Usage:
    bot-mmorpg-train --data data/raw --model efficientnet_lstm --epochs 10
    bot-mmorpg-train --data data/raw --model mobilenet_v3 --epochs 5 --batch-size 32
    bot-mmorpg-train --list-models
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

# PyTorch imports
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    # Stub classes for when PyTorch is not installed
    class Dataset:
        """Stub Dataset class when PyTorch is not installed."""
        pass
    class DataLoader:
        """Stub DataLoader class when PyTorch is not installed."""
        pass

# Local imports
try:
    from .models_pytorch import (
        get_model, list_models, get_model_info,
        save_model, count_parameters, get_device
    )
    MODELS_AVAILABLE = True
except ImportError as e:
    print(f"[Warning] Could not import models_pytorch: {e}")
    MODELS_AVAILABLE = False

# Fallback for direct script execution
if not MODELS_AVAILABLE:
    try:
        from models_pytorch import (
            get_model, list_models, get_model_info,
            save_model, count_parameters, get_device
        )
        MODELS_AVAILABLE = True
    except ImportError:
        MODELS_AVAILABLE = False

# Secure data loading
try:
    from ..utils.secure_loader import (
        load_training_data_secure,
        DataValidationError,
        UntrustedDataWarning
    )
    SECURE_LOADER_AVAILABLE = True
except ImportError:
    SECURE_LOADER_AVAILABLE = False
    load_training_data_secure = None
    DataValidationError = Exception
    UntrustedDataWarning = UserWarning


# =============================================================================
# Configuration (Legacy compatibility)
# =============================================================================

WIDTH = 480
HEIGHT = 270
LR = 1e-3
EPOCHS = 1
MODEL_NAME = 'model/mmorpg_bot'


# =============================================================================
# Dataset
# =============================================================================

class GameplayDataset(Dataset):
    """
    PyTorch Dataset for gameplay recordings.

    Loads .npy files containing (frame, action) pairs.
    Supports temporal windowing for LSTM-based models.
    """

    def __init__(
        self,
        data_dir: Path,
        seq_len: int = 1,
        transform=None,
        limit_files: Optional[int] = None,
        file_pattern: str = "training_data-*.npy",
    ):
        """
        Args:
            data_dir: Directory containing training_data-*.npy files
            seq_len: Number of consecutive frames per sample (for temporal models)
            transform: Optional transforms to apply
            limit_files: Limit number of files to load (for testing)
            file_pattern: Glob pattern for data files
        """
        self.data_dir = Path(data_dir)
        self.seq_len = seq_len
        self.transform = transform

        # Find all data files (support multiple patterns)
        patterns = [file_pattern, "preprocessed_training_data-*.npy"]
        self.files = []
        for pattern in patterns:
            self.files.extend(sorted(self.data_dir.glob(pattern)))

        # Remove duplicates and sort
        self.files = sorted(set(self.files))

        if limit_files:
            self.files = self.files[:limit_files]

        if not self.files:
            raise ValueError(f"No training data found in {data_dir}")

        print(f"[Dataset] Found {len(self.files)} data files")

        # Load all data into memory
        self._load_data()

    def _load_data(self):
        """Load all data files into memory with security validation."""
        all_frames = []
        all_actions = []

        for f in self.files:
            try:
                # Use secure loader if available for pickle safety
                if SECURE_LOADER_AVAILABLE and load_training_data_secure is not None:
                    try:
                        data = load_training_data_secure(
                            f, validate=True, allow_untrusted=True
                        )
                    except DataValidationError as e:
                        print(f"[Dataset] Security warning for {f}: {e}")
                        print("[Dataset] Skipping untrusted file")
                        continue
                else:
                    # Fallback to standard loading with pickle (legacy support)
                    # WARNING: Only use with trusted data sources
                    data = np.load(f, allow_pickle=True)

                for item in data:
                    if len(item) >= 2:
                        frame, action = item[0], item[1]
                        all_frames.append(frame)
                        all_actions.append(action)
            except Exception as e:
                print(f"[Dataset] Warning: Could not load {f}: {e}")

        if not all_frames:
            raise ValueError("No valid data loaded from files")

        self.frames = np.array(all_frames)
        self.actions = np.array(all_actions, dtype=np.float32)

        print(f"[Dataset] Loaded {len(self.frames)} samples")
        print(f"[Dataset] Frame shape: {self.frames[0].shape}")
        print(f"[Dataset] Action shape: {self.actions[0].shape}")

    def __len__(self) -> int:
        return max(0, len(self.frames) - self.seq_len + 1)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Get a training sample."""
        # Get sequence of frames
        if self.seq_len > 1:
            frames = self.frames[idx:idx + self.seq_len]
        else:
            frames = self.frames[idx:idx + 1]

        # Get action for last frame in sequence
        action = self.actions[idx + self.seq_len - 1]

        # Convert to tensor (NCHW format for PyTorch)
        frames = torch.tensor(frames, dtype=torch.float32)
        frames = frames.permute(0, 3, 1, 2)  # (seq, C, H, W)
        frames = frames / 255.0  # Normalize to [0, 1]

        # Remove sequence dim if seq_len == 1
        if self.seq_len == 1:
            frames = frames.squeeze(0)

        action = torch.tensor(action, dtype=torch.float32)

        return frames, action


# =============================================================================
# Training Functions
# =============================================================================

def train_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    optimizer: optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
    epoch: int,
) -> float:
    """Train for one epoch."""
    model.train()
    total_loss = 0.0
    num_batches = len(dataloader)

    for batch_idx, (frames, actions) in enumerate(dataloader):
        frames = frames.to(device)
        actions = actions.to(device)

        # Forward pass
        optimizer.zero_grad()
        outputs = model(frames)
        loss = criterion(outputs, actions)

        # Backward pass
        loss.backward()

        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        optimizer.step()

        total_loss += loss.item()

        # Progress
        if (batch_idx + 1) % 10 == 0 or batch_idx == num_batches - 1:
            print(f"  Batch {batch_idx + 1}/{num_batches} - Loss: {loss.item():.4f}")

    return total_loss / num_batches


def validate(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Tuple[float, float]:
    """Validate the model."""
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for frames, actions in dataloader:
            frames = frames.to(device)
            actions = actions.to(device)

            outputs = model(frames)
            loss = criterion(outputs, actions)
            total_loss += loss.item()

            # Calculate accuracy (for multi-label, use threshold)
            preds = (torch.sigmoid(outputs) > 0.5).float()
            correct += (preds == actions).all(dim=1).sum().item()
            total += actions.size(0)

    avg_loss = total_loss / len(dataloader) if len(dataloader) > 0 else 0.0
    accuracy = correct / total if total > 0 else 0.0

    return avg_loss, accuracy


def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: Optional[DataLoader],
    device: torch.device,
    epochs: int = 10,
    learning_rate: float = 1e-4,
    save_dir: Path = Path("artifacts/model"),
    model_name: str = "model",
) -> nn.Module:
    """Full training loop with validation and checkpointing."""
    model = model.to(device)

    # Optimizer and scheduler
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.01)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    # Loss function (multi-label binary cross-entropy)
    criterion = nn.BCEWithLogitsLoss()

    # Training history
    best_val_loss = float('inf')

    print(f"\n{'='*60}")
    print("Training Configuration")
    print(f"{'='*60}")
    print(f"  Model: {model.__class__.__name__}")
    print(f"  Parameters: {count_parameters(model):,}")
    print(f"  Device: {device}")
    print(f"  Epochs: {epochs}")
    print(f"  Learning Rate: {learning_rate}")
    print(f"  Train Batches: {len(train_loader)}")
    if val_loader:
        print(f"  Val Batches: {len(val_loader)}")
    print(f"{'='*60}\n")

    for epoch in range(epochs):
        epoch_start = time.time()
        print(f"Epoch {epoch + 1}/{epochs}")
        print("-" * 40)

        # Train
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device, epoch)

        # Validate
        if val_loader:
            val_loss, val_acc = validate(model, val_loader, criterion, device)
            print(f"  Train Loss: {train_loss:.4f}")
            print(f"  Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}")

            # Save best model
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                save_path = save_dir / f"{model_name}_best.pth"
                save_model(
                    model, str(save_path),
                    optimizer=optimizer,
                    epoch=epoch,
                    loss=val_loss,
                    model_name=model.__class__.__name__,
                )
                print(f"  Saved best model to {save_path}")
        else:
            print(f"  Train Loss: {train_loss:.4f}")

        # Step scheduler
        scheduler.step()

        # Checkpoint every 5 epochs
        if (epoch + 1) % 5 == 0:
            save_path = save_dir / f"{model_name}_epoch{epoch + 1}.pth"
            save_model(model, str(save_path), optimizer=optimizer, epoch=epoch, loss=train_loss)
            print(f"  Checkpoint saved to {save_path}")

        epoch_time = time.time() - epoch_start
        print(f"  Time: {epoch_time:.1f}s\n")

    # Save final model
    save_path = save_dir / f"{model_name}_final.pth"
    save_model(model, str(save_path), optimizer=optimizer, epoch=epochs - 1)
    print(f"Final model saved to {save_path}")

    return model


# =============================================================================
# Main
# =============================================================================

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="BOT-MMORPG-AI Model Training (PyTorch)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--data", default="data/raw", help="Folder with .npy files")
    parser.add_argument("--out", default="artifacts/model", help="Folder to save model")
    parser.add_argument("--model", default="efficientnet_lstm", help="Model architecture")
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--seq-len", type=int, default=4, help="Sequence length for temporal models")
    parser.add_argument("--num-actions", type=int, default=29, help="Number of output actions")
    parser.add_argument("--val-split", type=float, default=0.1, help="Validation split ratio")
    parser.add_argument("--no-pretrained", action="store_true", help="Don't use pretrained weights")
    parser.add_argument("--cpu", action="store_true", help="Force CPU training")
    parser.add_argument("--list-models", action="store_true", help="List available models")
    parser.add_argument("--limit-files", type=int, help="Limit number of data files (for testing)")

    args = parser.parse_args(argv)

    # List models and exit
    if args.list_models:
        if not MODELS_AVAILABLE:
            print("[Error] models_pytorch.py not found")
            return 1
        print("\nAvailable Models:")
        print("=" * 60)
        for name in list_models():
            info = get_model_info(name)
            rec = " [RECOMMENDED]" if info.get("recommended") else ""
            print(f"\n  {name}{rec}")
            print(f"    {info['description']}")
            print(f"    Params: {info['params']}, Inference: {info['inference_ms']}")
        return 0

    # Check dependencies
    if not PYTORCH_AVAILABLE:
        print("[Error] PyTorch not available. Install with: pip install torch torchvision")
        return 1

    if not MODELS_AVAILABLE:
        print("[Error] models_pytorch.py not found")
        return 1

    # Paths
    data_dir = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not data_dir.exists():
        print(f"[Error] Data directory not found: {data_dir}")
        return 1

    # Device
    device = torch.device("cpu") if args.cpu else get_device()

    print(f"\n{'='*60}")
    print("BOT-MMORPG-AI Training")
    print(f"{'='*60}")
    print(f"Data: {data_dir}")
    print(f"Output: {out_dir}")
    print(f"Model: {args.model}")
    print(f"Device: {device}")

    # Check if model is temporal
    model_info = get_model_info(args.model)
    is_temporal = model_info.get("temporal", False)
    seq_len = args.seq_len if is_temporal else 1

    print(f"Temporal: {is_temporal} (seq_len={seq_len})")

    # Create dataset
    print("\nLoading data...")
    try:
        dataset = GameplayDataset(data_dir, seq_len=seq_len, limit_files=args.limit_files)
    except ValueError as e:
        print(f"[Error] {e}")
        return 1

    # Split train/val
    total_size = len(dataset)
    val_size = int(total_size * args.val_split)
    train_size = total_size - val_size

    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])

    print(f"Train samples: {len(train_dataset)}")
    print(f"Val samples: {len(val_dataset)}")

    # Create dataloaders
    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True,
        num_workers=0, pin_memory=device.type == "cuda",
    )

    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0,
    ) if val_size > 0 else None

    # Create model
    print(f"\nCreating model: {args.model}")
    model = get_model(
        args.model, num_actions=args.num_actions,
        temporal_frames=seq_len, pretrained=not args.no_pretrained,
    )

    print(f"Parameters: {count_parameters(model):,}")

    # Train
    print("\nStarting training...")
    model = train_model(
        model=model, train_loader=train_loader, val_loader=val_loader,
        device=device, epochs=args.epochs, learning_rate=args.lr,
        save_dir=out_dir, model_name=args.model,
    )

    print(f"\n{'='*60}")
    print("Training Complete!")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
