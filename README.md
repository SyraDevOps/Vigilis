```markdown
# Vigilis 1.0v

Sistema de classificação de imagens com treinamento, download automático de imagens e explicação visual (Grad-CAM).

## Pré-requisitos

- Python 3.8+
- [PyTorch](https://pytorch.org/)
- [torchvision](https://pytorch.org/vision/stable/index.html)
- [icrawler](https://github.com/hellock/icrawler)
- Outros pacotes: `numpy`, `pillow`, `scikit-learn`, `matplotlib`, `opencv-python`

Instale as dependências com:

```sh
pip install -r requirements.txt
pip install torch torchvision icrawler opencv-python
```

## 1. Baixar imagens automaticamente

Para baixar imagens de uma classe (exemplo: "foguete"):

```sh
python download_images.py --classe foguete --quantidade 100
```

As imagens serão baixadas e organizadas em `data/train/foguete` e `data/valid/foguete`.

Repita para cada classe desejada.

## 2. Treinar o modelo

Após baixar imagens para todas as classes, treine o modelo:

```sh
python train.py
```

O modelo treinado será salvo em `models/trained_model.pt`.

## 3. Classificar imagens

Para classificar uma imagem:

```sh
python classify.py --image caminho/para/imagem.jpg
```

Para classificar todas as imagens de uma pasta:

```sh
python classify.py --folder caminho/para/pasta
```

Para gerar visualização Grad-CAM (explicação visual):

```sh
python classify.py --image caminho/para/imagem.jpg --gradcam
```

## 4. Estrutura de Pastas

```
data/
  train/
    classe1/
    classe2/
    ...
  valid/
    classe1/
    classe2/
    ...
  classify/
models/
src/
```

## 5. Configurações

Edite `src/config.py` para ajustar parâmetros como tamanho das imagens, número de épocas, batch size, etc.

---

**Dúvidas?**  
Abra um issue ou consulte os comentários nos arquivos fonte.
```
