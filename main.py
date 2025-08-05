import os
import csv
import easyocr
from PIL import Image

PASTA_IMAGENS = "img"
PASTA_TEXTOS = "extracted_texts"
ARQUIVO_SAIDA = "resultados.csv"

def setup_folders():
    """Create output folder if it doesn't exist."""
    if not os.path.exists(PASTA_TEXTOS):
        os.makedirs(PASTA_TEXTOS)

def extract_text_from_image(reader, image_path):
    """Extract all text from image using OCR."""
    # Get raw text results with position information
    results = reader.readtext(image_path)
    
    # Convert results to structured data
    extracted_data = {
        'raw_text': [],
        'metadata': {
            'observer': '',
            'location': '',
            'receiver': '',
            'antenna': '',
            'frequencies': []
        }
    }
    
    for (bbox, text, prob) in results:
        text = text.strip()
        extracted_data['raw_text'].append(text)
        
        # Extract metadata
        if "Observer" in text:
            extracted_data['metadata']['observer'] = text.split(":")[-1].strip()
        elif "Receiving Location" in text:
            extracted_data['metadata']['location'] = text.split(":")[-1].strip()
        elif "Receiver" in text and "Receiving" not in text:
            extracted_data['metadata']['receiver'] = text.split(":")[-1].strip()
        elif "antenna" in text.lower():
            extracted_data['metadata']['antenna'] = text.split(":")[-1].strip()
        
        # Try to extract frequency values (assuming they're numeric)
        try:
            if any(char.isdigit() for char in text):
                freq = float(text.replace("kHz", "").strip())
                extracted_data['metadata']['frequencies'].append(freq)
        except ValueError:
            pass
    
    return extracted_data

def save_text_file(filename, data):
    """Save extracted text to a file."""
    output_path = os.path.join(PASTA_TEXTOS, f"{os.path.splitext(filename)[0]}.txt")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # Write metadata section
        f.write("=== METADATA ===\n")
        f.write(f"Observer: {data['metadata']['observer']}\n")
        f.write(f"Location: {data['metadata']['location']}\n")
        f.write(f"Receiver: {data['metadata']['receiver']}\n")
        f.write(f"Antenna: {data['metadata']['antenna']}\n")
        
        if data['metadata']['frequencies']:
            f.write("\n=== FREQUENCIES ===\n")
            for freq in data['metadata']['frequencies']:
                f.write(f"{freq} kHz\n")
        
        # Write raw text section
        f.write("\n=== RAW TEXT ===\n")
        for text in data['raw_text']:
            f.write(f"{text}\n")

def process_images():
    """Process all PNG images in the specified folder."""
    setup_folders()
    
    # Initialize OCR reader
    reader = easyocr.Reader(['en'], gpu=False)
    
    # Get all PNG files
    image_files = [f for f in os.listdir(PASTA_IMAGENS) if f.lower().endswith('.png')]
    
    # Process each image
    for image_file in image_files:
        image_path = os.path.join(PASTA_IMAGENS, image_file)
        print(f"📷 Processing {image_file}...")
        
        try:
            # Extract text and metadata from image
            extracted_data = extract_text_from_image(reader, image_path)
            
            # Save to individual text file
            save_text_file(image_file, extracted_data)
            
            print(f"✅ Saved text file for {image_file}")
            
        except Exception as e:
            print(f"❌ Error processing {image_file}: {str(e)}")
            continue

if __name__ == "__main__":
    process_images()
