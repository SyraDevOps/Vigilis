import os
import csv
from datetime import datetime

PASTA_TEXTOS = "./extracted_texts"
ARQUIVO_SAIDA = "./detections.csv"

def parse_text_file(file_path):
    """Parse a single text file and extract detection data."""
    detection = {
        'filename': os.path.basename(file_path),
        'date': '',
        'time': '',
        'observer': '',
        'location': '',
        'receiver': '',
        'antenna': '',
        'frequencies': [],
        'frame_range': ''
    }
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    section = ''
    for line in lines:
        line = line.strip()
        
        if line.startswith('==='):
            section = line
            continue
            
        if not line:
            continue
            
        # Extract metadata
        if 'Observer:' in line:
            detection['observer'] = line.split(':', 1)[1].strip()
        elif 'Location:' in line:
            detection['location'] = line.split(':', 1)[1].strip()
        elif 'Receiver:' in line:
            detection['receiver'] = line.split(':', 1)[1].strip()
        elif 'Antenna:' in line:
            detection['antenna'] = line.split(':', 1)[1].strip()
        
        # Extract date and time from filename pattern (e.g., "25.01.01 00:00")
        if line.count('.') >= 2 and (':' in line or '.' in line):
            try:
                parts = line.split()
                if len(parts) >= 2:
                    detection['date'] = parts[0]
                    detection['time'] = parts[1]
            except:
                pass
                
        # Extract frequencies
        if 'kHz' in line and section == '=== FREQUENCIES ===':
            try:
                freq = float(line.replace('kHz', '').strip())
                detection['frequencies'].append(freq)
            except:
                pass
                
        # Extract frame range from raw text
        if line.replace(',', '').replace('.', '').replace('-', '').strip().isdigit():
            if not detection['frame_range']:
                detection['frame_range'] = line.strip()
            
    # Convert frequencies list to string
    detection['frequencies'] = '; '.join(map(str, detection['frequencies']))
    
    return detection

def process_text_files():
    """Process all text files and create CSV."""
    detections = []
    
    # Get all text files
    text_files = [f for f in os.listdir(PASTA_TEXTOS) if f.endswith('.txt')]
    
    print(f"Found {len(text_files)} text files to process...")
    
    # Process each file
    for text_file in text_files:
        file_path = os.path.join(PASTA_TEXTOS, text_file)
        try:
            detection = parse_text_file(file_path)
            detections.append(detection)
            print(f"✅ Processed {text_file}")
        except Exception as e:
            print(f"❌ Error processing {text_file}: {str(e)}")
    
    # Sort detections by date and time
    detections.sort(key=lambda x: (x['date'], x['time']))
    
    # Save to CSV
    if detections:
        fieldnames = ['filename', 'date', 'time', 'observer', 'location', 
                     'receiver', 'antenna', 'frequencies', 'frame_range']
        
        with open(ARQUIVO_SAIDA, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(detections)
            
        print(f"\n✅ Successfully saved {len(detections)} detections to {ARQUIVO_SAIDA}")
    else:
        print("❌ No detections found to save")

if __name__ == "__main__":
    process_text_files()