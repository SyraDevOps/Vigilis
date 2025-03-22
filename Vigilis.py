from ultralytics import YOLO
import cv2

# Carregar o modelo treinado
model = YOLO('./last.pt')

# Carregar a imagem
image_path = './Syra.png'
image = cv2.imread(image_path)

# Realizar a predição
results = model.predict(image)

# Mostrar os resultados
for result in results:
    boxes = result.boxes.xyxy
    for box in boxes:
        x1, y1, x2, y2 = map(int, box[:4])
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)

# Exibir a imagem com as predições
cv2.imshow('Resultado', image)
cv2.waitKey(0)
cv2.destroyAllWindows()