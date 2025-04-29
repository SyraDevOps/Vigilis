import os
import torch
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
from model import MyModel
from config import Config

def detect_classes():
    train_classes = os.listdir(Config.train_dir)  # Corrigido para usar 'train_dir'
    valid_classes = os.listdir(Config.valid_dir)  # Corrigido para usar 'valid_dir'
    if set(train_classes) != set(valid_classes):
        raise ValueError("As classes em 'train' e 'valid' não correspondem.")
    return train_classes

def train_model(epochs):
    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Data transformations
    transform = transforms.Compose([
        transforms.Resize((Config.image_resize, Config.image_resize)),  # Corrigido para usar 'image_resize'
        transforms.CenterCrop(Config.image_crop),  # Corrigido para usar 'image_crop'
        transforms.ToTensor(),
    ])

    # Load datasets
    if not os.path.exists(Config.train_dir) or not os.path.exists(Config.valid_dir):  # Corrigido para usar 'train_dir' e 'valid_dir'
        raise FileNotFoundError("As pastas de treino ou validação não existem. Verifique os dados.")

    train_classes = detect_classes()
    print(f"Classes detectadas: {train_classes}")

    train_dataset = ImageFolder(root=Config.train_dir, transform=transform)  # Corrigido para usar 'train_dir'
    valid_dataset = ImageFolder(root=Config.valid_dir, transform=transform)  # Corrigido para usar 'valid_dir'

    train_loader = DataLoader(train_dataset, batch_size=Config.batch_size, shuffle=True)  # Corrigido para usar 'batch_size'
    valid_loader = DataLoader(valid_dataset, batch_size=Config.batch_size, shuffle=False)  # Corrigido para usar 'batch_size'

    # Initialize model, loss function, and optimizer
    model = MyModel(num_classes=len(train_dataset.classes)).to(device)
    criterion = torch.nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=Config.learning_rate)  # Corrigido para usar 'learning_rate'

    # Training loop
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        print(f'Epoch [{epoch+1}/{epochs}], Loss: {running_loss/len(train_loader):.4f}')

        # Validation step
        model.eval()
        correct = 0
        total = 0

        with torch.no_grad():
            for images, labels in valid_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

        print(f'Validation Accuracy: {100 * correct / total:.2f}%')

    # Save the trained model
    os.makedirs(Config.models_dir, exist_ok=True)  # Corrigido para usar 'models_dir'
    model_path = os.path.join(Config.models_dir, "trained_model.pt")  # Corrigido para usar 'models_dir'
    torch.save(model.state_dict(), model_path)
    print(f"Modelo salvo em: {model_path}")

if __name__ == "__main__":
    train_model(epochs=Config.epochs)  # Corrigido para usar 'epochs'