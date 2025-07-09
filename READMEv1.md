Aqui está um **README completo** para o sistema **VIGIS**, baseado no seu código:

---

# 🛰️ VIGIS — Sistema Inteligente de Classificação de Imagens

**VIGIS** (Visual Intelligent Grid Image System) é uma solução completa para **coleta, organização, treinamento e classificação de imagens** utilizando redes neurais convolucionais com PyTorch. Ele oferece um pipeline completo, desde o download de imagens até a geração de explicações visuais por Grad-CAM.

---

## 📂 Estrutura do Projeto

```
vigis/
├── classify.py           # Classificação de imagens + Grad-CAM
├── config.py             # Parâmetros globais e diretórios
├── data_loader.py        # Datasets e DataLoaders com tratamento
├── download_images.py    # Coleta automática de imagens via Bing
├── model.py              # Definição da arquitetura da rede neural
├── train.py              # Treinamento do modelo
├── models/               # Modelos treinados (.pt)
└── data/
    ├── train/            # Imagens de treinamento (por classe)
    ├── valid/            # Imagens de validação (por classe)
    └── classify/         # Imagens a serem classificadas
```

---

## 🚀 Funcionalidades

* 🔍 **Coleta automática de dados** (via Bing) por categoria
* 🧠 **Modelo leve CNN personalizado**
* 🏋️‍♀️ **Treinamento supervisionado** com validação automática
* 🖼️ **Classificação de imagens individuais ou em lote**
* 🔥 **Grad-CAM** para visualizar onde o modelo “olha”
* 📦 Estrutura extensível e modular
* ✅ Suporte a múltiplas classes

---

## 📦 Requisitos

* Python 3.8+
* PyTorch
* torchvision
* Pillow
* numpy
* matplotlib
* icrawler
* OpenCV (`opencv-python`)

Instale via:

```bash
pip install torch torchvision pillow numpy matplotlib icrawler opencv-python
```

---

## 🧱 Como usar

### 1. 🔽 Baixar imagens por classe

```bash
python download_images.py --classe "foguete" --quantidade 100
```

Isso irá baixar imagens do Bing, dividir automaticamente em `train` e `valid`, e organizá-las nas pastas apropriadas.

---

### 2. 🏋️‍♂️ Treinar o modelo

```bash
python train.py
```

O modelo será treinado com os dados de `data/train` e `data/valid`, e salvo em `models/trained_model.pt`.

---

### 3. 🧪 Classificar imagens

#### Classificar uma imagem:

```bash
python classify.py --image path/para/imagem.jpg --gradcam
```

#### Classificar todas as imagens de uma pasta:

```bash
python classify.py --folder path/para/pasta/ --gradcam
```

O parâmetro `--gradcam` é opcional, mas gera uma sobreposição visual mostrando as regiões importantes para a decisão do modelo.

---

## 🧠 Modelo

O modelo é uma **CNN simples**, com uma camada convolucional + maxpool e um classificador totalmente conectado:

```python
Conv2d(3, 64, 3) → ReLU → MaxPool(2)
→ Flatten → Linear(64×112×112 → 128) → ReLU → Linear(128 → classes)
```

---

## 🔬 Explicabilidade com Grad-CAM

O `classify.py` inclui suporte à geração automática de Grad-CAM para qualquer imagem classificada. Isso ajuda a interpretar **por que** o modelo tomou determinada decisão.

---

## 🛠️ Personalização

Parâmetros como tamanho das imagens, batch size, número de épocas e caminhos estão definidos no arquivo [`config.py`](config.py), podendo ser facilmente ajustados para novos experimentos.

---

## 🤖 Futuras melhorias

* 📊 Interface Web ou Dashboard com Streamlit
* 🔁 Treinamento incremental ou contínuo
* ☁️ Integração com serviços de nuvem
* 📈 Relatórios e gráficos de desempenho automáticos

---

## 👨‍💻 Desenvolvido por

**Syra DevOps** • Construindo soluções robustas e inteligentes para visão computacional e IA.

---

Se quiser que eu gere esse README como `README.md`, é só avisar!
