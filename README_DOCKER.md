# Docker Deployment Guide

這份指南將協助您使用 Docker 啟動 ABC 策略選股系統。

## 1. 安裝 Docker
如果您還沒安裝 Docker，請前往官網下載並安裝 **Docker Desktop**：
- [下載 Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)

安裝後請啟動 Docker Desktop，並確保左下角顯示為綠色的 "Engine running"。

## 2. 啟動應用程式
在專案根目錄 (`e:\01-antigravity-AI\09_PY_STOCK`) 開啟終端機 (PowerShell 或 CMD)，執行以下指令：

```powershell
docker-compose up --build
```

這個指令會自動：
1.  建立後端 Python 環境。
2.  建立前端 React 環境並編譯成靜態檔。
3.  啟動 Nginx 網頁伺服器。

## 3. 使用系統
啟動完成後，請打開瀏覽器訪問：

- **http://localhost**

(不再是 localhost:5173，因為已經打包成正式版了)

## 4. 常見指令
- **停止服務**：在終端機按 `Ctrl + C`，或執行 `docker-compose down`。
- **背景執行**：使用 `docker-compose up -d --build` (不會佔用終端機)。
- **查看 Logs**：`docker-compose logs -f`。

## 注意事項
- **API Key**: 目前使用 `docker-compose.yml` 內的預設 Key，若要更改請直接編輯該檔案中的 `GEMINI_API_KEY`。
- **快取**: `yf_cache` 資料夾會被掛載到容器內，所以快取資料會保留在您的硬碟上。
