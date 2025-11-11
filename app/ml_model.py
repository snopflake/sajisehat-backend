# app/ml_model.py
import os
from typing import Dict

import torch
import torch.nn as nn
from torchvision.models import resnet18, ResNet18_Weights
from torchvision import transforms
from PIL import Image

# === stats dari Colab (ISI DENGAN ANGKA ASLI DARI COLAB) ===
SERVING_MEAN = 52.9655
SERVING_STD  = 65.58435281947975
PACK_MEAN    = 5.615
PACK_STD     = 7.7184373418458225
SUGAR_MEAN   = 11.13
SUGAR_STD    = 6.447720527442238


# --- definisi model HARUS sama persis dengan di Colab ---
class NutritionNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.backbone = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
        in_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Identity()
        self.head = nn.Linear(in_features, 3)

    def forward(self, x):
        feats = self.backbone(x)
        out = self.head(feats)

        serving_size = out[:, 0]
        servings_per_pack = out[:, 1]
        sugar_per_serving = out[:, 2]

        return {
            "serving_size_gram": serving_size,
            "servings_per_pack": servings_per_pack,
            "sugar_per_serving_gram": sugar_per_serving,
        }

# --- device & transform untuk inference ---
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

img_size = 224
inference_transform = transforms.Compose([
    transforms.Resize((img_size, img_size)),
    transforms.ToTensor(),
])

# --- load model sekali di awal dan cache di _model ---
_model: NutritionNet | None = None

def load_nutrition_model() -> NutritionNet:
    global _model
    if _model is not None:
        return _model

    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "ml", "best_nutrition_model.pth")

    model = NutritionNet().to(device)

    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    _model = model
    return _model

def predict_nutrition_from_pil(image: Image.Image) -> Dict[str, float]:
    model = load_nutrition_model()

    if image.mode != "RGB":
        image = image.convert("RGB")

    x = inference_transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        outputs = model(x)

    # z-score dari model
    serving_z = float(outputs["serving_size_gram"][0].cpu().item())
    pack_z    = float(outputs["servings_per_pack"][0].cpu().item())
    sugar_z   = float(outputs["sugar_per_serving_gram"][0].cpu().item())

    # un-normalize ke skala asli
    serving_real = serving_z * SERVING_STD + SERVING_MEAN
    pack_real    = pack_z    * PACK_STD    + PACK_MEAN
    sugar_real   = sugar_z   * SUGAR_STD   + SUGAR_MEAN

    # post-process / clamp ringan
    serving_real = max(0.0, min(serving_real, 300.0))   # 0–300 g
    sugar_real   = max(0.0, min(sugar_real, 50.0))      # 0–50 g
    pack_real    = max(1.0, min(pack_real, 40.0))       # 1–40 porsi

    # bulatkan servings_per_pack
    servings_per_pack_rounded = int(round(pack_real))
    if servings_per_pack_rounded < 1:
        servings_per_pack_rounded = 1

    return {
        "serving_size_gram": round(serving_real, 2),
        "servings_per_pack": servings_per_pack_rounded,
        "sugar_per_serving_gram": round(sugar_real, 2),
    }
