import os
import shutil
import random
from icrawler.builtin import BingImageCrawler

def ensure_class_directories(classes):
    """
    Garante que as pastas para as classes existam.
    Args:
        classes: Lista de nomes de classes.
    """
    for class_name in classes:
        train_dir = f"data/train/{class_name}"
        valid_dir = f"data/valid/{class_name}"
        os.makedirs(train_dir, exist_ok=True)
        os.makedirs(valid_dir, exist_ok=True)

def download_and_organize_images(class_name, num_images, train_split=0.8):
    """
    Baixa imagens do Bing e organiza nas pastas de treino e validação.
    Args:
        class_name: Nome da classe (ex: 'foguete')
        num_images: Número de imagens para baixar
        train_split: Proporção de imagens para treino (0.8 = 80%)
    """
    # Configurar diretórios
    temp_dir = "data/temp"
    train_dir = f"data/train/{class_name}"
    valid_dir = f"data/valid/{class_name}"
    
    # Criar diretórios necessários
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(train_dir, exist_ok=True)
    os.makedirs(valid_dir, exist_ok=True)
    
    print(f"Baixando {num_images} imagens para a classe '{class_name}'...")
    
    try:
        # Baixar imagens usando icrawler
        crawler = BingImageCrawler(storage={"root_dir": temp_dir})
        crawler.crawl(keyword=class_name, max_num=num_images)
        
        # Diretório onde as imagens foram baixadas
        source_dir = temp_dir
        
        # Verificar se o diretório temporário contém imagens
        if not os.path.exists(source_dir):
            raise FileNotFoundError(f"O diretório temporário '{source_dir}' não foi encontrado.")
        
        # Listar imagens baixadas
        images = [f for f in os.listdir(source_dir) 
                 if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
        
        if not images:
            raise FileNotFoundError("Nenhuma imagem foi encontrada no diretório temporário.")
        
        random.shuffle(images)
        
        # Calcular divisão treino/validação
        split_idx = int(len(images) * train_split)
        train_images = images[:split_idx]
        valid_images = images[split_idx:]
        
        # Mover imagens para pasta de treino
        for i, img in enumerate(train_images):
            src = os.path.join(source_dir, img)
            dst = os.path.join(train_dir, f"{class_name}_{i:03d}{os.path.splitext(img)[1]}")
            if os.path.exists(src):
                shutil.copy2(src, dst)
            
        # Mover imagens para pasta de validação
        for i, img in enumerate(valid_images):
            src = os.path.join(source_dir, img)
            dst = os.path.join(valid_dir, f"{class_name}_{i:03d}{os.path.splitext(img)[1]}")
            if os.path.exists(src):
                shutil.copy2(src, dst)
            
        print(f"Organizadas {len(train_images)} imagens para treino e {len(valid_images)} para validação")
    
    except Exception as e:
        print(f"Erro ao baixar/organizar imagens: {e}")
    
    finally:
        # Limpar diretório temporário
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def get_classes():
    """Retorna lista de classes baseada nas pastas existentes"""
    train_dir = "data/train"
    if os.path.exists(train_dir):
        return sorted([d for d in os.listdir(train_dir) 
                      if os.path.isdir(os.path.join(train_dir, d))])
    return []

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Baixa e organiza imagens do Bing")
    parser.add_argument("--classe", type=str, help="Nome da classe (ex: foguete)")
    parser.add_argument("--quantidade", type=int, default=100, 
                      help="Quantidade de imagens para baixar")
    args = parser.parse_args()
    
    if args.classe:
        download_and_organize_images(args.classe, args.quantidade)
    else:
        # Garante que as pastas para todas as classes existam
        classes = get_classes()
        ensure_class_directories(classes)
        print("\nClasses disponíveis:", classes)