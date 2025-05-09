import cv2

# Carrega o classificador pré-treinado para detecção de rosto
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Abre a webcam
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Erro: Não foi possível acessar a câmera.")
    exit()

while True:
    # Captura frame a frame
    ret, frame = cap.read()
    if not ret:
        print("Erro ao capturar o frame.")
        break

    # Converte o frame para escala de cinza (melhor para detecção)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detecta os rostos
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

    # Para cada rosto detectado, desenha uma bounding box
    for (x, y, w, h) in faces:
        # Desenha o retângulo em volta do rosto
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

    # Exibe o frame resultante
    cv2.imshow('Face Tracker', frame)

    # Sai do loop se pressionar 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Libera a câmera e fecha as janelas
cap.release()
cv2.destroyAllWindows()
