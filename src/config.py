"""
Configurações para o sistema de classificação de imagens.
"""

import os

# Classes para classificação (serão detectadas automaticamente)
CLASSES = None  # Detectar automaticamente com base nas pastas

# Parâmetros de treinamento
BATCH_SIZE = 32
NUM_EPOCHS = 15
LEARNING_RATE = 0.001

# Parâmetros de processamento de imagens
IMAGE_RESIZE = 256
IMAGE_CROP = 224

# Caminhos
DATA_DIR = 'data'
TRAIN_DIR = f'{DATA_DIR}/train'
VALID_DIR = f'{DATA_DIR}/valid'
CLASSIFY_DIR = f'{DATA_DIR}/classify'  # Pasta para imagens a serem classificadas
MODELS_DIR = 'models'

# Criar pasta para classificação, se não existir
os.makedirs(CLASSIFY_DIR, exist_ok=True)

class Config:
    learning_rate = LEARNING_RATE
    epochs = NUM_EPOCHS
    batch_size = BATCH_SIZE
    image_resize = IMAGE_RESIZE
    image_crop = IMAGE_CROP
    train_dir = TRAIN_DIR  # Adicionado
    valid_dir = VALID_DIR  # Adicionado
    models_dir = MODELS_DIR
    classify_dir = CLASSIFY_DIR