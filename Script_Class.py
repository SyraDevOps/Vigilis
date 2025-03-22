import xml.etree.ElementTree as ET
import os

xml_dir = 'labels/xml'  # Caminho para os arquivos XML

classes = set()  # Usando um set para evitar duplicatas

# Percorrendo todos os arquivos XML no diretório
for xml_file in os.listdir(xml_dir):
    if xml_file.endswith('.xml'):
        tree = ET.parse(os.path.join(xml_dir, xml_file))
        root = tree.getroot()
        
        # Para cada objeto no arquivo XML, pegar o nome da classe
        for obj in root.findall('object'):
            class_name = obj.find('name').text
            classes.add(class_name)  # Adiciona ao set (sem duplicatas)

# Convertendo o set para uma lista e ordenando (opcional)
classes = sorted(list(classes))

print("Classes encontradas:", classes)
