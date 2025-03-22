import os
import random

# Diretório das imagens
image_dir = "img"  # Substitua pelo caminho correto

# Listar todas as imagens
images = [os.path.join(image_dir, img) for img in os.listdir(image_dir) if img.endswith((".jpg", ".png", ".jpeg"))]

# Embaralhar as imagens
random.shuffle(images)

# Definir porcentagem de treino e validação
train_ratio = 0.8  # 80% das imagens para treino
train_size = int(len(images) * train_ratio)

# Separar imagens para treino e validação
train_images = images[:train_size]
val_images = images[train_size:]

# Salvar os arquivos
with open("train.txt", "w") as f:
    f.writelines("\n".join(train_images))

with open("val.txt", "w") as f:
    f.writelines("\n".join(val_images))

print("Arquivos train.txt e val.txt gerados com sucesso!")
