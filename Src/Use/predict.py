# src/Use/predict.py

import torch
from PIL import Image
from torchvision import transforms
from src.models.meteor_model import MeteorClassifier  # <-- import corrigido

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
IMAGE_SIZE = 128

transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.5], [0.5])
])

model = MeteorClassifier().to(DEVICE)
model.load_state_dict(torch.load('models/meteor_model.pth', map_location=DEVICE))
model.eval()

def predict_image(path):
    image = Image.open(path).convert('RGB')
    img_tensor = transform(image).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        output = model(img_tensor)
        pred = output.item() > 0.5
        print(f"{path} → {'Meteoro' if pred else 'Sem meteoro'} ({output.item():.4f})")

# Exemplo de uso
predict_image("exemplo.jpg")
