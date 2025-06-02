package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
)

type CameraViewer struct {
	cameras       []string
	currentIndex  int
	autoNext      bool
	failedCameras map[int]bool
}

type PageData struct {
	Cameras       []CameraData
	CurrentIndex  int
	CurrentCamera string
	AutoNext      bool
	Log           []string
}

type CameraData struct {
	Index  int
	URL    string
	Status string
}

type CountryData struct {
	Countries map[string]struct {
		Count int `json:"count"`
	} `json:"countries"`
}

var viewer *CameraViewer
var logMessages []string

const htmlTemplate = `
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Visualizador de Câmeras IP</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 10px; background: #f0f0f0; }
        .container { max-width: 1400px; margin: 0 auto; display: grid; grid-template-columns: 300px 1fr; gap: 20px; }
        .controls { background: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .main-content { background: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .camera-list { max-height: 400px; overflow-y: auto; border: 1px solid #ddd; }
        .camera-item { padding: 8px; border-bottom: 1px solid #eee; cursor: pointer; }
        .camera-item:hover { background: #f5f5f5; }
        .camera-item.active { background: #e3f2fd; }
        .camera-item.failed { color: #d32f2f; }
        .buttons { margin: 10px 0; }
        .btn { padding: 8px 12px; margin: 2px; background: #2196F3; color: white; border: none; border-radius: 3px; cursor: pointer; }
        .btn:hover { background: #1976D2; }
        .btn.stop { background: #f44336; }
        .btn.auto { background: #4CAF50; }
        .video-container { text-align: center; min-height: 400px; display: flex; align-items: center; justify-content: center; background: #000; }
        .video-container img { max-width: 100%; max-height: 500px; }
        .info { margin: 10px 0; padding: 10px; background: #e8f5e8; border-radius: 3px; }
        .log { max-height: 200px; overflow-y: auto; background: #f5f5f5; padding: 10px; border-radius: 3px; font-family: monospace; font-size: 12px; }
        .status { padding: 5px; margin: 5px 0; }
        .refresh { animation: spin 2s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
    <script>
        let autoRefresh = false;
        let refreshInterval;
        
        function selectCamera(index) {
            fetch('/select/' + index, {method: 'POST'})
                .then(() => location.reload());
        }
        
        function playCamera() {
            fetch('/play', {method: 'POST'})
                .then(() => location.reload());
        }
        
        function stopCamera() {
            fetch('/stop', {method: 'POST'})
                .then(() => location.reload());
        }
        
        function nextCamera() {
            fetch('/next', {method: 'POST'})
                .then(() => location.reload());
        }
        
        function prevCamera() {
            fetch('/prev', {method: 'POST'})
                .then(() => location.reload());
        }
        
        function toggleAutoNext() {
            fetch('/toggle-auto', {method: 'POST'})
                .then(() => location.reload());
        }
        
        function searchCameras() {
            document.getElementById('search-btn').innerHTML = '🔄 Buscando...';
            document.getElementById('search-btn').classList.add('refresh');
            fetch('/search', {method: 'POST'})
                .then(() => {
                    setTimeout(() => location.reload(), 3000);
                });
        }
        
        function reloadList() {
            fetch('/reload', {method: 'POST'})
                .then(() => location.reload());
        }
        
        // Auto-refresh da imagem a cada 2 segundos
        setInterval(() => {
            const img = document.getElementById('camera-image');
            if (img && img.src.includes('/stream')) {
                img.src = '/stream?' + Date.now();
            }
        }, 2000);
    </script>
</head>
<body>
    <div class="container">
        <div class="controls">
            <h3>Controles</h3>
            <div class="buttons">
                <button class="btn" onclick="playCamera()">▶ Play</button>
                <button class="btn stop" onclick="stopCamera()">⏸ Stop</button>
                <button class="btn" onclick="prevCamera()">⏮ Anterior</button>
                <button class="btn" onclick="nextCamera()">⏭ Próxima</button>
                <button class="btn auto" onclick="toggleAutoNext()">🔄 Auto Next {{if .AutoNext}}ON{{else}}OFF{{end}}</button>
            </div>
            
            <div class="status">
                <strong>Câmera Atual:</strong><br>
                {{if .CurrentCamera}}
                    {{.CurrentIndex}}/{{len .Cameras}}: {{.CurrentCamera}}
                {{else}}
                    Nenhuma selecionada
                {{end}}
            </div>
            
            <h3>Câmeras ({{len .Cameras}})</h3>
            <div class="camera-list">
                {{range .Cameras}}
                <div class="camera-item {{if eq .Index $.CurrentIndex}}active{{end}} {{if eq .Status "failed"}}failed{{end}}" 
                     onclick="selectCamera({{.Index}})">
                    {{if eq .Status "failed"}}❌{{else}}📹{{end}} {{printf "%3d" (add .Index 1)}}. {{.URL}}
                </div>
                {{end}}
            </div>
            
            <div class="buttons">
                <button class="btn" onclick="reloadList()">🔄 Recarregar</button>
                <button class="btn" id="search-btn" onclick="searchCameras()">🔍 Buscar Novas</button>
            </div>
        </div>
        
        <div class="main-content">
            <h2>Visualizador de Câmeras IP</h2>
            
            <div class="video-container">
                {{if .CurrentCamera}}
                    <img id="camera-image" src="/stream?{{.CurrentIndex}}" alt="Stream da câmera" 
                         onerror="this.src='/static/error.jpg'">
                {{else}}
                    <div style="color: white;">Selecione uma câmera para visualizar</div>
                {{end}}
            </div>
            
            <div class="info">
                <strong>Status:</strong> 
                {{if .CurrentCamera}}
                    Conectado à câmera {{add .CurrentIndex 1}}
                {{else}}
                    Aguardando seleção
                {{end}}
            </div>
            
            <h3>Log de Eventos</h3>
            <div class="log">
                {{range .Log}}
                    {{.}}<br>
                {{end}}
            </div>
        </div>
    </div>
</body>
</html>
`

func addLog(message string) {
	timestamp := time.Now().Format("15:04:05")
	logLine := fmt.Sprintf("[%s] %s", timestamp, message)
	logMessages = append(logMessages, logLine)

	// Mantém apenas os últimos 50 logs
	if len(logMessages) > 50 {
		logMessages = logMessages[len(logMessages)-50:]
	}

	fmt.Println(logLine)
}

func (cv *CameraViewer) loadCameras() error {
	file, err := os.Open("cameras_insecam.txt")
	if err != nil {
		addLog("Arquivo cameras_insecam.txt não encontrado")
		return err
	}
	defer file.Close()

	cv.cameras = cv.cameras[:0]
	scanner := bufio.NewScanner(file)

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" {
			cv.cameras = append(cv.cameras, line)
		}
	}

	addLog(fmt.Sprintf("Carregadas %d câmeras", len(cv.cameras)))
	return nil
}

func (cv *CameraViewer) fetchCamerasFromInsecam() {
	addLog("Iniciando busca por novas câmeras...")

	client := &http.Client{Timeout: 15 * time.Second}

	// Busca países
	resp, err := client.Get("http://www.insecam.org/en/jsoncountries/")
	if err != nil {
		addLog(fmt.Sprintf("Erro ao buscar países: %v", err))
		return
	}
	defer resp.Body.Close()

	var countryData CountryData
	if err := json.NewDecoder(resp.Body).Decode(&countryData); err != nil {
		addLog(fmt.Sprintf("Erro ao decodificar JSON: %v", err))
		return
	}

	addLog(fmt.Sprintf("Encontrados %d países", len(countryData.Countries)))

	file, err := os.Create("cameras_insecam.txt")
	if err != nil {
		addLog(fmt.Sprintf("Erro ao criar arquivo: %v", err))
		return
	}
	defer file.Close()

	totalCameras := 0
	processedCountries := 0

	for country := range countryData.Countries {
		if processedCountries >= 3 {
			break
		}

		addLog(fmt.Sprintf("Processando: %s", country))

		for page := 1; page <= 2; page++ {
			url := fmt.Sprintf("http://www.insecam.org/en/bycountry/%s/?page=%d", country, page)

			resp, err := client.Get(url)
			if err != nil {
				break
			}

			doc, err := goquery.NewDocumentFromReader(resp.Body)
			resp.Body.Close()
			if err != nil {
				break
			}

			camerasFound := 0
			doc.Find("img[src]").Each(func(i int, s *goquery.Selection) {
				src, exists := s.Attr("src")
				if !exists {
					return
				}

				if strings.Contains(src, "mjpg") || strings.Contains(src, "jpg") || strings.Contains(src, "jpeg") {
					var cameraURL string
					if strings.HasPrefix(src, "//") {
						cameraURL = "http:" + src
					} else if !strings.HasPrefix(src, "/") {
						cameraURL = src
					} else {
						return
					}

					file.WriteString(cameraURL + "\n")
					camerasFound++
					totalCameras++
				}
			})

			if camerasFound == 0 {
				break
			}
			time.Sleep(2 * time.Second)
		}
		processedCountries++
	}

	addLog(fmt.Sprintf("Busca completa! %d câmeras encontradas", totalCameras))
	cv.failedCameras = make(map[int]bool)
	cv.loadCameras()
}

func indexHandler(w http.ResponseWriter, r *http.Request) {
	tmpl := template.Must(template.New("index").Funcs(template.FuncMap{
		"add": func(a, b int) int { return a + b },
	}).Parse(htmlTemplate))

	cameras := make([]CameraData, len(viewer.cameras))
	for i, camera := range viewer.cameras {
		status := "ok"
		if viewer.failedCameras[i] {
			status = "failed"
		}
		cameras[i] = CameraData{
			Index:  i,
			URL:    camera,
			Status: status,
		}
	}

	currentCamera := ""
	if viewer.currentIndex < len(viewer.cameras) {
		currentCamera = viewer.cameras[viewer.currentIndex]
	}

	data := PageData{
		Cameras:       cameras,
		CurrentIndex:  viewer.currentIndex,
		CurrentCamera: currentCamera,
		AutoNext:      viewer.autoNext,
		Log:           logMessages,
	}

	tmpl.Execute(w, data)
}

func streamHandler(w http.ResponseWriter, r *http.Request) {
	if viewer.currentIndex >= len(viewer.cameras) {
		http.Error(w, "Nenhuma câmera selecionada", http.StatusNotFound)
		return
	}

	cameraURL := viewer.cameras[viewer.currentIndex]

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(cameraURL)
	if err != nil {
		addLog(fmt.Sprintf("Erro ao conectar: %v", err))
		viewer.failedCameras[viewer.currentIndex] = true
		http.Error(w, "Erro na câmera", http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		addLog(fmt.Sprintf("Status HTTP: %d", resp.StatusCode))
		viewer.failedCameras[viewer.currentIndex] = true
		http.Error(w, "Câmera não disponível", http.StatusInternalServerError)
		return
	}

	// Remove da lista de falhas se funcionou
	delete(viewer.failedCameras, viewer.currentIndex)

	w.Header().Set("Content-Type", resp.Header.Get("Content-Type"))
	io.Copy(w, resp.Body)
}

func selectHandler(w http.ResponseWriter, r *http.Request) {
	indexStr := strings.TrimPrefix(r.URL.Path, "/select/")
	index, err := strconv.Atoi(indexStr)
	if err != nil || index < 0 || index >= len(viewer.cameras) {
		http.Error(w, "Índice inválido", http.StatusBadRequest)
		return
	}

	viewer.currentIndex = index
	addLog(fmt.Sprintf("Câmera %d selecionada", index+1))
	w.WriteHeader(http.StatusOK)
}

func nextHandler(w http.ResponseWriter, r *http.Request) {
	if len(viewer.cameras) > 0 {
		viewer.currentIndex = (viewer.currentIndex + 1) % len(viewer.cameras)
		addLog(fmt.Sprintf("Próxima câmera: %d", viewer.currentIndex+1))
	}
	w.WriteHeader(http.StatusOK)
}

func prevHandler(w http.ResponseWriter, r *http.Request) {
	if len(viewer.cameras) > 0 {
		viewer.currentIndex = (viewer.currentIndex - 1 + len(viewer.cameras)) % len(viewer.cameras)
		addLog(fmt.Sprintf("Câmera anterior: %d", viewer.currentIndex+1))
	}
	w.WriteHeader(http.StatusOK)
}

func toggleAutoHandler(w http.ResponseWriter, r *http.Request) {
	viewer.autoNext = !viewer.autoNext
	status := "DESATIVADO"
	if viewer.autoNext {
		status = "ATIVADO"
	}
	addLog(fmt.Sprintf("Auto Next: %s", status))
	w.WriteHeader(http.StatusOK)
}

func searchHandler(w http.ResponseWriter, r *http.Request) {
	go viewer.fetchCamerasFromInsecam()
	w.WriteHeader(http.StatusOK)
}

func reloadHandler(w http.ResponseWriter, r *http.Request) {
	viewer.loadCameras()
	w.WriteHeader(http.StatusOK)
}

func main() {
	viewer = &CameraViewer{
		cameras:       make([]string, 0),
		currentIndex:  0,
		autoNext:      false,
		failedCameras: make(map[int]bool),
	}

	// Carrega câmeras existentes
	viewer.loadCameras()

	// Rotas HTTP
	http.HandleFunc("/", indexHandler)
	http.HandleFunc("/stream", streamHandler)
	http.HandleFunc("/select/", selectHandler)
	http.HandleFunc("/next", nextHandler)
	http.HandleFunc("/prev", prevHandler)
	http.HandleFunc("/play", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	http.HandleFunc("/stop", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	http.HandleFunc("/toggle-auto", toggleAutoHandler)
	http.HandleFunc("/search", searchHandler)
	http.HandleFunc("/reload", reloadHandler)

	port := "8080"
	addLog(fmt.Sprintf("Servidor iniciado em http://localhost:%s", port))
	addLog("Abra seu navegador e acesse a URL acima")

	log.Fatal(http.ListenAndServe(":"+port, nil))
}
