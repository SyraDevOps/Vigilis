import os
import torch
from PIL import Image
from torchvision import transforms
from model import MyModel
from config import Config

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

def classify_images(model_path, image_paths):
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
        except Exception as e:
            print(f"Erro ao classificar imagem {image_path}: {e}")
    
    return results

def main():
    """Função principal para classificação via linha de comando."""
    import argparse
    parser = argparse.ArgumentParser(description="Classificação de imagens usando modelo treinado.")
    parser.add_argument("--model", type=str, default=f"{Config.models_dir}/trained_model.pt",  # Corrigido para usar 'models_dir'
                        help="Caminho para o modelo treinado.")
    parser.add_argument("--image", type=str, help="Caminho para a imagem a ser classificada.")
    parser.add_argument("--folder", type=str, help="Caminho para a pasta contendo imagens a serem classificadas.")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"Modelo não encontrado: {args.model}")
        return

    if args.image:
        if not os.path.exists(args.image):
            print(f"Imagem não encontrada: {args.image}")
            return
        results = classify_images(args.model, [args.image])
        for image_path, class_name in results.items():
            print(f"{image_path}: {class_name}")
    elif args.folder:
        if not os.path.exists(args.folder):
            print(f"Pasta não encontrada: {args.folder}")
            return
        image_paths = [os.path.join(args.folder, f) for f in os.listdir(args.folder)
                       if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
        results = classify_images(args.model, image_paths)
        print("Resultados da classificação:")
        print("--------------------------------------------------")
        for image_path, class_name in results.items():
            print(f"{os.path.basename(image_path)}: {class_name}")
    else:
        print("Por favor, forneça uma imagem (--image) ou uma pasta (--folder) para classificação.")

if __name__ == "__main__":
    main()