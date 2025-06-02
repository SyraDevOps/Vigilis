import requests
from bs4 import BeautifulSoup
import time

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def buscar_cameras_insecam():
    url = "http://www.insecam.org/en/jsoncountries/"
    
    try:
        # Primeiro, pegamos a lista de países
        res = requests.get(url, headers=headers)
        paises = res.json()['countries']
        
        print(f"Encontrados {len(paises)} países com câmeras públicas.\n")
        
        with open("cameras_insecam.txt", "w", encoding='utf-8') as f:
            total_cameras = 0
            
            # REMOVIDO: [:5] - agora processa TODOS os países
            for pais in paises.keys():
                print(f"[+] País: {pais} | Quantidade: {paises[pais]['count']}")
                
                pagina = 0
                # REMOVIDO: while pagina < 3 - agora processa TODAS as páginas
                while True:
                    pagina += 1
                    url_pagina = f"http://www.insecam.org/en/bycountry/{pais}/?page={pagina}"
                    
                    try:
                        resposta = requests.get(url_pagina, headers=headers, timeout=15)
                        soup = BeautifulSoup(resposta.text, 'html.parser')
                        
                        # Procura por diferentes seletores possíveis
                        streams = soup.find_all('img', {'src': True})
                        
                        cameras_encontradas = 0
                        for img in streams:
                            src = img.get('src')
                            if src and ('mjpg' in src or 'jpg' in src or 'jpeg' in src):
                                # Se a URL não começa com http, adiciona o protocolo
                                if src.startswith('//'):
                                    camera_url = 'http:' + src
                                elif src.startswith('/'):
                                    camera_url = 'http://www.insecam.org' + src
                                else:
                                    camera_url = src
                                
                                print(f"Câmera encontrada: {camera_url}")
                                f.write(camera_url + "\n")
                                cameras_encontradas += 1
                                total_cameras += 1
                        
                        if cameras_encontradas == 0:
                            print(f"Nenhuma câmera encontrada na página {pagina} - fim do país {pais}")
                            break
                        
                        print(f"Página {pagina}: {cameras_encontradas} câmeras encontradas")
                        time.sleep(3)  # Pausa maior para evitar bloqueio
                        
                    except Exception as e:
                        print(f"[!] Erro ao carregar página {url_pagina}: {e}")
                        break
                
                print(f"Finalizou país {pais} - Total até agora: {total_cameras}\n")
        
        print(f"\n[✓] BUSCA COMPLETA! Total de {total_cameras} câmeras salvas em 'cameras_insecam.txt'.")
        
    except Exception as e:
        print(f"Erro geral: {e}")

# Executar o script
if __name__ == "__main__":
    buscar_cameras_insecam()