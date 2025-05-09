import cv2
import numpy as np

# Carregar o classificador Haar Cascade para detecção de rostos
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Inicializar a captura de vídeo
cap = cv2.VideoCapture(0)

# Lista para armazenar rostos já registrados (pode ser um array de vetores)
registered_faces = []
registered_names = []

# Criar uma janela para exibir as regiões das faces comparadas
cv2.namedWindow("Regioes Comparadas", cv2.WINDOW_NORMAL)

while True:
    # Capturar um frame do vídeo
    ret, frame = cap.read()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detectar rostos no frame
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    for (x, y, w, h) in faces:
        # Cortar a face da imagem
        face_roi = gray[y:y+h, x:x+w]
        
        match_found = False
        name = ""

        for registered_face, registered_name in zip(registered_faces, registered_names):
            # Usar a comparação de histograma para ver se a face já foi registrada
            hist1 = cv2.calcHist([face_roi], [0], None, [256], [0, 256])
            hist2 = cv2.calcHist([registered_face], [0], None, [256], [0, 256])

            # Comparar os histogramas usando a métrica de correlação
            correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

            # Definir um limiar para considerar faces como iguais
            if correlation > 0.9:
                match_found = True
                name = registered_name
                break

        if not match_found:
            # Registrar a nova face
            print("Novo rosto detectado! Digite o nome da pessoa: ")
            name = input()
            registered_faces.append(face_roi)
            registered_names.append(name)
        
        # Exibir o nome na tela de captura
        cv2.putText(frame, name, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # Destacar a face com um retângulo
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        # Mostrar a face comparada na janela ao lado
        face_comparison_window = frame.copy()
        cv2.rectangle(face_comparison_window, (x, y), (x + w, y + h), (0, 255, 0), 2)
        face_roi_color = frame[y:y+h, x:x+w]
        cv2.imshow("Regioes Comparadas", face_roi_color)

    # Exibir o frame com a detecção de rosto
    cv2.imshow('Face Detection', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
