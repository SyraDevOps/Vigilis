from ultralytics import YOLO

# Caminhos dos arquivos de configuração e dados
data_yaml = './data.yaml'  # Arquivo de configuração dos dados
weights = './vigilis.pt'  # Pesos pré-treinados do seu modelo YOLO12

# Parâmetros de treinamento
epochs = 100  # Número de épocas de treinamento
batch_size = 16  # Tamanho do lote

# Função para treinar o modelo
def train_model():
    model = YOLO(weights)  # Carregar o modelo com os pesos fornecidos
    model.train(
        data=data_yaml,
        epochs=epochs,
        batch=batch_size,  # Corrigido para 'batch'
        project='Vigilis',  # Nome do projeto
        name='exp'  # Nome da experiência
    )

if __name__ == '__main__':
    train_model()