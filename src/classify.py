import os
import torch
import numpy as np
from PIL import Image
from torchvision import transforms
from model import MyModel
from config import Config
import matplotlib.pyplot as plt
import cv2

def load_model(model_path, num_classes):
    """Carrega o modelo treinado."""
    try:
        model = MyModel(num_classes=num_classes)
        model.load_state_dict(torch.load(model_path))
        model.eval()
        return model
    except Exception as e:
        print(f"Erro ao carregar o modelo: {e}")
        return None

def classify_image(model, image):
    """Classifica uma única imagem."""
    preprocess = transforms.Compose([
        transforms.Resize((Config.image_resize, Config.image_resize)),
        transforms.CenterCrop(Config.image_crop),
        transforms.ToTensor(),
    ])

    image_tensor = preprocess(image).unsqueeze(0)  # Adicionar dimensão de lote
    
    with torch.no_grad():
        output = model(image_tensor)
    
    _, predicted = torch.max(output, 1)
    return predicted.item()

def get_last_conv_layer(model):
    """Encontra a última camada convolucional do modelo."""
    for layer in reversed(model.features):
        if isinstance(layer, torch.nn.Conv2d):
            return layer
    raise ValueError("Nenhuma camada convolucional encontrada no modelo.")

def generate_gradcam(model, image_path, class_idx, output_path="gradcam.jpg"):
    """Gera um mapa de influência (Grad-CAM) para a imagem."""
    model.eval()

    # Transformar a imagem
    preprocess = transforms.Compose([
        transforms.Resize((Config.image_resize, Config.image_resize)),
        transforms.CenterCrop(Config.image_crop),
        transforms.ToTensor(),
    ])
    image = Image.open(image_path).convert('RGB')
    input_tensor = preprocess(image).unsqueeze(0)

    # Obter a última camada convolucional
    target_layer = get_last_conv_layer(model)
    gradients = []

    def save_gradient(grad):
        gradients.append(grad)

    # Registrar hook para capturar gradientes
    handle = target_layer.register_backward_hook(lambda module, grad_input, grad_output: save_gradient(grad_output[0]))

    # Forward pass
    output = model(input_tensor)
    model.zero_grad()

    # Backward pass para a classe alvo
    class_score = output[0, class_idx]
    class_score.backward()

    # Obter gradientes e ativação
    gradient = gradients[0].squeeze(0).cpu().numpy()
    activation = target_layer(input_tensor).squeeze(0).detach().cpu().numpy()

    # Calcular Grad-CAM
    weights = np.mean(gradient, axis=(1, 2))
    gradcam = np.zeros(activation.shape[1:], dtype=np.float32)

    for i, w in enumerate(weights):
        gradcam += w * activation[i]

    gradcam = np.maximum(gradcam, 0)
    gradcam = cv2.resize(gradcam, (Config.image_crop, Config.image_crop))
    gradcam = gradcam - gradcam.min()
    gradcam = gradcam / gradcam.max()

    # Sobrepor Grad-CAM na imagem original
    heatmap = cv2.applyColorMap(np.uint8(255 * gradcam), cv2.COLORMAP_JET)
    heatmap = np.float32(heatmap) / 255
    image = np.array(image.resize((Config.image_crop, Config.image_crop))) / 255
    overlay = heatmap + image
    overlay = overlay / overlay.max()

    # Salvar a imagem com Grad-CAM
    plt.imsave(output_path, overlay)
    print(f"Grad-CAM salvo em: {output_path}")

    # Remover o hook
    handle.remove()

def classify_images(model_path, image_paths, generate_cam=False):
    """Classifica várias imagens e retorna resultados."""
    num_classes = len(os.listdir(Config.train_dir))
    model = load_model(model_path, num_classes)
    if not model:
        return {}
    
    results = {}
    classes = os.listdir(Config.train_dir)
    
    for image_path in image_paths:
        try:
            image = Image.open(image_path).convert('RGB')
            class_id = classify_image(model, image)
            class_name = classes[class_id] if class_id < len(classes) else "Desconhecido"
            results[image_path] = class_name

            # Gerar Grad-CAM, se solicitado
            if generate_cam:
                output_path = f"{os.path.splitext(image_path)[0]}_gradcam.jpg"
                generate_gradcam(model, image_path, class_id, output_path)

        except Exception as e:
            print(f"Erro ao classificar imagem {image_path}: {e}")
    
    return results

def main():
    """Função principal para classificação via linha de comando."""
    import argparse
    parser = argparse.ArgumentParser(description="Classificação de imagens usando modelo treinado.")
    parser.add_argument("--model", type=str, default=f"{Config.models_dir}/trained_model.pt",
                        help="Caminho para o modelo treinado.")
    parser.add_argument("--image", type=str, help="Caminho para a imagem a ser classificada.")
    parser.add_argument("--folder", type=str, help="Caminho para a pasta contendo imagens a serem classificadas.")
    parser.add_argument("--gradcam", action="store_true", help="Gera Grad-CAM para as imagens classificadas.")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"Modelo não encontrado: {args.model}")
        return

    if args.image:
        if not os.path.exists(args.image):
            print(f"Imagem não encontrada: {args.image}")
            return
        results = classify_images(args.model, [args.image], generate_cam=args.gradcam)
        for image_path, class_name in results.items():
            print(f"{image_path}: {class_name}")
    elif args.folder:
        if not os.path.exists(args.folder):
            print(f"Pasta não encontrada: {args.folder}")
            return
        image_paths = [os.path.join(args.folder, f) for f in os.listdir(args.folder)
                       if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
        results = classify_images(args.model, image_paths, generate_cam=args.gradcam)
        print("Resultados da classificação:")
        print("--------------------------------------------------")
        for image_path, class_name in results.items():
            print(f"{os.path.basename(image_path)}: {class_name}")
    else:
        print("Por favor, forneça uma imagem (--image) ou uma pasta (--folder) para classificação.")

if __name__ == "__main__":
    main()