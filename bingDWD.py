import os
import requests
from bs4 import BeautifulSoup

def download_images(query, num_images=100, folder="img"):
    if not os.path.exists(folder):
        os.makedirs(folder)

    headers = {"User-Agent": "Mozilla/5.0"}
    downloaded = 0
    page = 0

    while downloaded < num_images:
        search_url = f"https://www.bing.com/images/search?q={query}&first={page * 20}"
        response = requests.get(search_url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            img_tags = soup.find_all('img', class_='mimg')
            for idx, img_tag in enumerate(img_tags):
                if downloaded >= num_images:
                    break
                try:
                    img_url = img_tag.get('src') or img_tag.get('data-src') or img_tag.get('data-iurl')
                    if img_url and img_url.startswith("http"):
                        img_data = requests.get(img_url).content
                        ext = os.path.splitext(img_url)[1]
                        if ext.lower() not in ['.jpg', '.jpeg', '.png']:
                            ext = '.jpg'
                        with open(f"{folder}/image_{downloaded + 1}{ext}", "wb") as f:
                            f.write(img_data)
                        print(f"Imagem {downloaded + 1} baixada com sucesso!")
                        downloaded += 1
                except Exception as e:
                    print(f"Erro ao baixar a imagem {downloaded + 1}: {e}")
        else:
            print("Erro na requisição ao Bing:", response.status_code)
            break
        page += 1

# Testando a função
query = "planeta jupiter"
download_images(query, num_images=100)
