from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import BinaryClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image
import torch
from PIL import Image
from torchvision import transforms
import matplotlib.pyplot as plt
import numpy as np
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.models.meteor_model import MeteorClassifier

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

def get_last_conv_layer(model):
    for layer in reversed(list(model.modules())):
        if isinstance(layer, torch.nn.Conv2d):
            return layer
    raise ValueError("Nenhuma camada Conv2d encontrada no modelo")

def predict_image(path):
    image = Image.open(path).convert('RGB')
    img_tensor = transform(image).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        output = model(img_tensor)
        prob = output.item()
        pred = prob > 0.5
        label = 'Meteoro' if pred else 'Sem meteoro'
        print(f"{path} → {label} ({prob:.4f})")

    # Grad-CAM
    target_layer = get_last_conv_layer(model)

    cam = GradCAM(model=model, target_layers=[target_layer])
    targets = [BinaryClassifierOutputTarget(1 if pred else 0)]
    grayscale_cam = cam(input_tensor=img_tensor, targets=targets)[0]  # (H, W)

    # Visualização
    np_img = np.array(image.resize((IMAGE_SIZE, IMAGE_SIZE))).astype(np.float32) / 255.0
    visualization = show_cam_on_image(np_img, grayscale_cam, use_rgb=True)

    plt.imshow(visualization)
    plt.title(f'{label} ({prob:.4f})')
    plt.axis('off')
    plt.show()

# Exemplo
predict_image("t.jpg")
