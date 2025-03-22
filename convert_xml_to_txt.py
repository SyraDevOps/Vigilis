import os
import xml.etree.ElementTree as ET

# Diretórios de entrada e saída
xml_dir = 'labels/xml'  # Caminho para os arquivos XML
txt_dir = 'labels/txt'  # Caminho para salvar os arquivos TXT

# Mapeamento de classes (ajuste conforme necessário)
classes = ['classe1', 'classe2', 'classe3']  # Lista das suas classes

# Função para converter XML para formato YOLO
def convert_xml_to_yolo(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Abertura do arquivo de texto correspondente
    txt_file = os.path.join(txt_dir, os.path.basename(xml_file).replace('.xml', '.txt'))
    with open(txt_file, 'w') as f:
        for obj in root.findall('object'):
            class_name = obj.find('name').text
            class_id = classes.index(class_name)  # Obter ID da classe
            
            # Obtendo as coordenadas da caixa delimitadora
            xml_box = obj.find('bndbox')
            xmin = int(xml_box.find('xmin').text)
            ymin = int(xml_box.find('ymin').text)
            xmax = int(xml_box.find('xmax').text)
            ymax = int(xml_box.find('ymax').text)

            # Normalizando as coordenadas
            width = int(root.find('size/width').text)
            height = int(root.find('size/height').text)

            x_center = (xmin + xmax) / 2.0 / width
            y_center = (ymin + ymax) / 2.0 / height
            bbox_width = (xmax - xmin) / width
            bbox_height = (ymax - ymin) / height

            # Escrevendo no formato YOLO (class_id x_center y_center bbox_width bbox_height)
            f.write(f"{class_id} {x_center} {y_center} {bbox_width} {bbox_height}\n")

# Percorrendo todos os arquivos XML no diretório
for xml_file in os.listdir(xml_dir):
    if xml_file.endswith('.xml'):
        convert_xml_to_yolo(os.path.join(xml_dir, xml_file))

print("Conversão concluída!")
