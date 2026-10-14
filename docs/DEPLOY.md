# PigLedger Docker 部署（另保留）

目前建議使用 [Vercel 固定網址部署](VERCEL.md)。本頁保留自有主機的 Docker 方法；**尚未公開部署，沒有已驗證的正式網站網址。** Docker／Caddy 過往版本的隔離測試不等於本版正式網域驗收。

## 首次部署

1. 準備 Linux 主機、Docker Engine 與 Docker Compose v2。網域 A／AAAA 指向主機，防火牆允許80、443。只有實際設定 IPv6 的主機才建立 AAAA。主機需要下載 `python:3.12-slim`、`caddy:2.10-alpine`；Caddy 需對憑證簽發服務保持正常 TLS 與網路存取。
2. 上傳並解壓 `pigledger-1.0.0.zip`，進入 `pigledger-1.0.0/`：

   ```sh
   cp .env.example .env
   # 用文字編輯器把 FARM_DOMAIN 改為你的實際網域，例如 farm.example.com
   docker compose up -d --build
   docker compose exec app python -m app.manage create-admin --username YOUR_ADMIN
   ```

   管理員密碼由終端機隱藏輸入；不要放在指令參數、聊天或前端。請自行替換 `YOUR_ADMIN`。啟動前 compose 強制要求 `FARM_DOMAIN`。Caddy 自動申請並更新正式 TLS 憑證；不需停用憑證驗證。
3. 檢查：

   ```sh
   docker compose ps
   curl --fail https://YOUR_DOMAIN/api/health
   docker compose logs --tail 50 app web
   ```

   `YOUR_DOMAIN` 換成你的網域。健康檢查應回 `ok: true`、`version: 1.0.0`。用瀏覽器登入、建立棟舍與批次、登記一筆、重新整理確認；第二台裝置應看得到同一資料。請先用測試批次驗收，必要時由管理員更正刪除並保留歷程。
4. 管理員在「設定」建立登記與唯讀帳號。伺服器驗證所有修改權限；唯讀仍可匯出一般紀錄 CSV，不能下載含帳號雜湊的完整備份。
5. Android Chrome：選單 → 安裝／加入主畫面。iPhone／iPad Safari：分享 → 加入主畫面。請使用正式 HTTPS 網址；檔案預覽不是此 App 的使用方式。

程式不公開8080埠；瀏覽器只透過 Caddy 80／443。`PIGLEDGER_SECURE=1` 啟用 Secure Cookie 與 HSTS。伺服器程序以 UID10001 執行，資料庫及備份檔限制檔案權限。

## 備份與更新

- 定期用「設定 → 下載完整備份 JSON」，另存到主機以外的私密位置。JSON 含帳號密碼雜湊，請當作敏感備份保護。
- 主機 SQLite 完整備份：

  ```sh
  docker compose exec app python -m app.manage backup
  ```

  指令顯示 `/data/backups/...sqlite3` 路徑。可用 `docker compose cp app:/data/backups/...sqlite3 ./...sqlite3` 複製指定檔，妥善保管。不要在服務寫入時直接只複製主資料庫檔而忽略 WAL；管理命令使用 SQLite Backup API。
- 升級前完成外部備份。保留同一 compose 專案名稱／部署目錄與 `farm_data` volume，再更新來源檔案、版本標籤，執行 `docker compose up -d --build`。資料 schema 更新前會自動備份；不清庫、不重設帳號。不要執行 `docker compose down -v` 或 `docker volume rm`，這會刪除持久資料。
- 移到新主機請還原原 volume 的可靠 SQLite 備份，或先建立暫時管理員，再匯入 JSON。JSON 匯入以 ID 去重、保留目前較新資料；遇到需覆蓋的衝突會拒絕整批，應先核對，不能把舊備份當成強制覆蓋。
- 更換網址仍使用同一資料庫／volume，資料不隨網址消失，但 Cookie 可能需要重新登入及重新加入主畫面。
- Service Worker 不缓存 API 或帳號資料。新版安裝後於設定顯示更新按鈕；有未保存輸入或待重試請先完成。套用更新會清掉此 App 的舊版本靜態快取，不清除資料庫。

## 還原與檢查

還原前先備份目前資料，停用 app（`docker compose stop app`），使用經驗證的完整 SQLite 備份還原 `/data/pigledger.sqlite3`，確認檔案擁有者為10001，且移除的 WAL／SHM 僅屬已停用且已備份的資料庫。再啟動 app 並檢查登入、筆數、統計及備份；此為災難復原操作，請由熟悉 Docker volume 的管理員執行。一般合併請用 UI 的 JSON 匯入，不直接覆蓋正式資料。

若資料庫 schema 比 App 新，App 拒絕啟動；應使用對應新版，不能降版清庫。公網部署還需依主機平台安排備份排程、監測與存取限制；程式本身沒有預測／自動叫料排程。
