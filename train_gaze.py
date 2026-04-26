"""Train a personalized L2CS-Net (ResNet-18) gaze model."""

from __future__ import annotations

import json
import math
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torchvision import models
from tqdm import tqdm


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "training_data" / "processed"
TRAIN_PKL = DATA_DIR / "train_dataset.pkl"
VAL_PKL = DATA_DIR / "val_dataset.pkl"
MODELS_DIR = BASE_DIR / "models"
CHECKPOINT_DIR = MODELS_DIR / "checkpoints"
BEST_CKPT = CHECKPOINT_DIR / "best_model.pth"
LAST_CKPT = CHECKPOINT_DIR / "last_model.pth"


@dataclass
class TrainConfig:
    epochs: int = 50
    batch_size: int = 16
    lr: float = 1e-4
    weight_decay: float = 1e-5
    alpha: float = 1.0
    num_workers: int = 4
    patience: int = 10
    grad_clip: float = 1.0


class PersonalGazeDataset(Dataset):
    """Dataset for loading preprocessed gaze samples from pickle files."""

    def __init__(self, pkl_path: Path) -> None:
        self.pkl_path = pkl_path
        self.samples = self._load_samples()

    def _load_samples(self) -> List[Dict[str, object]]:
        try:
            with self.pkl_path.open("rb") as f:
                return pickle.load(f)
        except Exception as exc:
            raise RuntimeError("Failed to load dataset pickle") from exc

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, object]:
        sample = self.samples[idx]
        image = torch.tensor(sample["image"], dtype=torch.float32).permute(2, 0, 1)
        return {
            "image": image,
            "yaw": torch.tensor(sample["yaw"], dtype=torch.float32),
            "pitch": torch.tensor(sample["pitch"], dtype=torch.float32),
            "yaw_bin": torch.tensor(sample["yaw_bin"], dtype=torch.long),
            "pitch_bin": torch.tensor(sample["pitch_bin"], dtype=torch.long),
        }


class PersonalGazeNet(nn.Module):
    """ResNet-18 backbone with L2CS heads."""

    def __init__(self) -> None:
        super().__init__()
        backbone = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        self.backbone = nn.Sequential(*list(backbone.children())[:-1])
        self.fc_yaw_class = nn.Linear(512, 90)
        self.fc_pitch_class = nn.Linear(512, 90)
        self.fc_yaw_reg = nn.Linear(512, 1)
        self.fc_pitch_reg = nn.Linear(512, 1)

        # Freeze early layers
        for name, param in backbone.named_parameters():
            if name.startswith("layer1") or name.startswith("layer2"):
                param.requires_grad = False

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        features = self.backbone(x).flatten(1)
        return {
            "yaw_cls": self.fc_yaw_class(features),
            "pitch_cls": self.fc_pitch_class(features),
            "yaw_reg": self.fc_yaw_reg(features),
            "pitch_reg": self.fc_pitch_reg(features),
        }


def build_dataloaders(config: TrainConfig) -> Tuple[DataLoader, DataLoader]:
    if not TRAIN_PKL.exists() or not VAL_PKL.exists():
        raise FileNotFoundError("Dataset pickle files not found; run prep_data.py")

    train_ds = PersonalGazeDataset(TRAIN_PKL)
    val_ds = PersonalGazeDataset(VAL_PKL)

    pin_memory = torch.cuda.is_available()

    train_loader = DataLoader(
        train_ds,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        pin_memory=pin_memory,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        pin_memory=pin_memory,
    )
    return train_loader, val_loader


def compute_loss(
    outputs: Dict[str, torch.Tensor],
    yaw: torch.Tensor,
    pitch: torch.Tensor,
    yaw_bin: torch.Tensor,
    pitch_bin: torch.Tensor,
    alpha: float,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    ce = nn.CrossEntropyLoss()
    mse = nn.MSELoss()
    cls_loss = ce(outputs["yaw_cls"], yaw_bin) + ce(outputs["pitch_cls"], pitch_bin)
    reg_loss = mse(outputs["yaw_reg"].squeeze(1), yaw) + mse(outputs["pitch_reg"].squeeze(1), pitch)
    total = cls_loss + alpha * reg_loss
    return total, cls_loss, reg_loss


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> Tuple[float, float, float]:
    model.eval()
    total_loss = 0.0
    total_yaw_mae = 0.0
    total_pitch_mae = 0.0
    count = 0
    with torch.no_grad():
        for batch in loader:
            images = batch["image"].to(device)
            yaw = batch["yaw"].to(device)
            pitch = batch["pitch"].to(device)
            yaw_bin = batch["yaw_bin"].to(device)
            pitch_bin = batch["pitch_bin"].to(device)

            outputs = model(images)
            loss, _, _ = compute_loss(outputs, yaw, pitch, yaw_bin, pitch_bin, 1.0)
            total_loss += loss.item() * images.size(0)

            yaw_pred = outputs["yaw_reg"].squeeze(1)
            pitch_pred = outputs["pitch_reg"].squeeze(1)
            total_yaw_mae += torch.mean(torch.abs(yaw_pred - yaw)).item() * images.size(0)
            total_pitch_mae += torch.mean(torch.abs(pitch_pred - pitch)).item() * images.size(0)
            count += images.size(0)

    if count == 0:
        return 0.0, 0.0, 0.0

    val_loss = total_loss / count
    val_mae_yaw = math.degrees(total_yaw_mae / count)
    val_mae_pitch = math.degrees(total_pitch_mae / count)
    return val_loss, val_mae_yaw, val_mae_pitch


def save_checkpoint(
    path: Path,
    epoch: int,
    model: nn.Module,
    optimizer: optim.Optimizer,
    val_loss: float,
    val_mae_deg: Tuple[float, float],
    train_loss: float,
    config: TrainConfig,
) -> None:
    try:
        torch.save(
            {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_loss,
                "val_mae_deg": val_mae_deg,
                "train_loss": train_loss,
                "config": config.__dict__,
            },
            path,
        )
    except Exception as exc:
        print(f"⚠ Failed to save checkpoint: {exc}")


def load_checkpoint(model: nn.Module, optimizer: optim.Optimizer, path: Path) -> int:
    try:
        ckpt = torch.load(path, map_location="cpu")
        model.load_state_dict(ckpt["model_state_dict"])
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        return int(ckpt.get("epoch", 0))
    except Exception as exc:
        print(f"⚠ Failed to load checkpoint: {exc}")
        return 0


def main() -> None:
    print("🚀 Starting training")
    config = TrainConfig()

    if torch.cuda.is_available() and torch.cuda.get_device_properties(0).total_memory < 4 * 1024**3:
        config.batch_size = 8

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    try:
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError("Failed to create checkpoint directory") from exc

    model = PersonalGazeNet().to(device)
    optimizer = optim.Adam(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=config.epochs, eta_min=1e-6)

    start_epoch = 0
    if LAST_CKPT.exists():
        try:
            resume = input("Resume from last checkpoint? [y/n]: ").strip().lower()
        except Exception:
            resume = "n"
        if resume == "y":
            start_epoch = load_checkpoint(model, optimizer, LAST_CKPT)
            print(f"✓ Resuming from epoch {start_epoch}")

    best_val = float("inf")
    patience_counter = 0

    for epoch in range(start_epoch, config.epochs):
        model.train()
        train_loader, val_loader = build_dataloaders(config)
        total_loss = 0.0
        total_count = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch + 1}/{config.epochs}")
        try:
            for batch in pbar:
                images = batch["image"].to(device)
                yaw = batch["yaw"].to(device)
                pitch = batch["pitch"].to(device)
                yaw_bin = batch["yaw_bin"].to(device)
                pitch_bin = batch["pitch_bin"].to(device)

                optimizer.zero_grad()
                outputs = model(images)
                loss, _, _ = compute_loss(outputs, yaw, pitch, yaw_bin, pitch_bin, config.alpha)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip)
                optimizer.step()

                total_loss += loss.item() * images.size(0)
                total_count += images.size(0)
                pbar.set_postfix({"loss": f"{loss.item():.4f}"})
        except RuntimeError as exc:
            if "out of memory" in str(exc).lower():
                print("⚠ CUDA OOM detected. Reducing batch size and retrying.")
                torch.cuda.empty_cache()
                config.batch_size = max(2, config.batch_size // 2)
                continue
            raise

        scheduler.step()
        train_loss = total_loss / max(1, total_count)

        val_loss, val_mae_yaw, val_mae_pitch = evaluate(model, val_loader, device)
        lr = scheduler.get_last_lr()[0]

        msg = (
            f"Epoch {epoch + 1}/{config.epochs} | Loss: {train_loss:.3f} | "
            f"Val MAE: Yaw={val_mae_yaw:.2f}° Pitch={val_mae_pitch:.2f}° | LR: {lr:.2e}"
        )

        if val_loss < best_val:
            best_val = val_loss
            patience_counter = 0
            save_checkpoint(BEST_CKPT, epoch + 1, model, optimizer, val_loss, (val_mae_yaw, val_mae_pitch), train_loss, config)
            msg += " ✓ BEST"
        else:
            patience_counter += 1

        save_checkpoint(LAST_CKPT, epoch + 1, model, optimizer, val_loss, (val_mae_yaw, val_mae_pitch), train_loss, config)
        print(msg)

        if (epoch + 1) % 10 == 0 and torch.cuda.is_available():
            mem_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            mem_used = torch.cuda.memory_allocated() / (1024**3)
            pct = (mem_used / mem_total) * 100 if mem_total > 0 else 0.0
            print(f"GPU Memory: {mem_used:.2f} GB / {mem_total:.2f} GB ({pct:.0f}%)")

        if patience_counter >= config.patience:
            print("⚠ Early stopping triggered")
            break

    if best_val > 0 and (val_mae_yaw > 3.5 or val_mae_pitch > 3.0):
        print("⚠ Target accuracy not reached. Consider collecting more data.")

    print("✓ Training complete")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"✗ Fatal error: {exc}")
        sys.exit(1)

