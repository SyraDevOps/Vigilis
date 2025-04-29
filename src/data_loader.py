import os
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
import config

class ImageDataset(Dataset):
    def __init__(self, data_dir, transform=None):
        self.data_dir = data_dir
        self.transform = transform
        self.classes = os.listdir(data_dir)
        self.class_to_idx = {cls: i for i, cls in enumerate(self.classes)}
        self.images = self._load_images()
        
    def _load_images(self):
        images = []
        for class_name in self.classes:
            class_dir = os.path.join(self.data_dir, class_name)
            if not os.path.isdir(class_dir):
                continue
                
            for filename in os.listdir(class_dir):
                # Filtrar apenas imagens com extensões comuns
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
                    img_path = os.path.join(class_dir, filename)
                    images.append((img_path, self.class_to_idx[class_name]))
        
        return images
    
    def __len__(self):
        return len(self.images)
    
    def __getitem__(self, idx):
        img_path, label = self.images[idx]
        try:
            # Lidar com imagens problemáticas
            img = Image.open(img_path).convert('RGB')
            if self.transform:
                img = self.transform(img)
            return img, label
        except Exception as e:
            print(f"Erro ao processar imagem {img_path}: {e}")
            # Retornar uma imagem substituta e o mesmo rótulo
            fallback_img = torch.zeros((3, config.IMAGE_CROP, config.IMAGE_CROP))
            return fallback_img, label

def get_transforms(train=True):
    """Retorna transformações para processamento de imagens com tamanho dinâmico."""
    if train and config.USE_AUGMENTATION:
        return transforms.Compose([
            transforms.Resize(config.IMAGE_RESIZE),
            transforms.RandomResizedCrop(config.IMAGE_CROP),
            transforms.RandomHorizontalFlip(p=0.5 if config.HORIZONTAL_FLIP else 0),
            transforms.RandomRotation(config.ROTATION_DEGREES),
            transforms.ColorJitter(
                brightness=config.BRIGHTNESS_VARIATION,
                contrast=config.CONTRAST_VARIATION
            ),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
    else:
        return transforms.Compose([
            transforms.Resize(config.IMAGE_RESIZE),
            transforms.CenterCrop(config.IMAGE_CROP),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

def get_dataloaders():
    """Cria e retorna dataloaders para conjuntos de treino e validação."""
    train_transform = get_transforms(train=True)
    valid_transform = get_transforms(train=False)
    
    train_dataset = ImageDataset(config.TRAIN_DIR, transform=train_transform)
    valid_dataset = ImageDataset(config.VALID_DIR, transform=valid_transform)
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.BATCH_SIZE,
        shuffle=True,
        num_workers=4,
        pin_memory=True
    )
    
    valid_loader = DataLoader(
        valid_dataset,
        batch_size=config.BATCH_SIZE,
        shuffle=False,
        num_workers=4,
        pin_memory=True
    )
    
    return train_loader, valid_loader