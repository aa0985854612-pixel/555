# PigLedger 1.3.1：固定雲端網址

正式網站：[https://555-rho-nine.vercel.app/](https://555-rho-nine.vercel.app/)。Vercel 團隊 pig13、專案555、GitHub aa0985854612-pixel/555 的 main。2026-10-15：普通 App 原始碼部署已 Ready；Turso 已連接並私密搬入原帳號、原始 Excel、紀錄與操作歷程，沒有清空原庫。

真實雲端的搬移、內容核對與既有帳號後端登入已完成；正式網址瀏覽器登入、跨裝置與實體手機驗收尚未完成。維護環境直接連線正式網站被網路代理403阻擋。詳見 [1.3.1 測試報告](TEST_REPORT_1.3.1.md)，不要將 Ready 誤當全部使用情境都已驗收。

## 手機及每日使用

Safari 或 Chrome 開正式 HTTPS 網址，登入原帳號，再使用「加入主畫面」。手機不用下載 ZIP、執行 bat 或透過檔案預覽開 HTML；筆電不用保持開機。

每日登記頁填豬隻異動；飼料頁分別登記到料及實際耗料；秤重頁登記頭數與重量；週期統計自動整理。資料不足顯示「—」或資料不足。完整說明見 [USER_GUIDE.md](USER_GUIDE.md)。

## 後續程式更新

以 GitHub main 部署 repository 根目錄（`vercel.json`、`pyproject.toml`、`api/`、`app/`）。Framework Preset 為 Other，Python3.12，無須指定其他 framework 或輸出目錄。保留 Production 的兩項伺服器環境變數：

| 名稱 | 內容 |
| --- | --- |
| `TURSO_DATABASE_URL` | 原 Turso 資料庫的 libsql／HTTPS 網址 |
| `TURSO_AUTH_TOKEN` | 同一資料庫的可讀寫金鑰，使用敏感值 |

環境變數修改後需重新部署才生效。不要把 token 放入聊天、GitHub、網址或 `NEXT_PUBLIC_` 欄位。維護代理的 VERCEL_TOKEN、TURSO_API_TOKEN 與 App 登入密碼不同，不需要放入 App 網站。

更新沿用相同雲端資料庫，不重新建庫、不重新匯入過時備份、不重設帳號。需要重新登入不代表資料遺失。1.3.1 的雲端版本標記使用 `cloud_metadata`，避免提供者拒絕 `PRAGMA user_version=3`；本地 schema3 不變，舊雲端版本標記仍可讀。

## 首次搬移到另一個空白資料庫（維護人員）

目前正式資料庫已搬移完成；以下只適用受控搬家，不是每次部署步驟。先停用日常寫入，確認目標是正確空白資料庫，使用原資料庫的 SQLite Backup API 製作備份。安全提供目標的 TURSO_DATABASE_URL、TURSO_AUTH_TOKEN，在 repository 根目錄執行：

```sh
python3 scripts/migrate_cloud.py --db /private/path/pigledger.sqlite3
```

來源檔不存在時拒絕建立新庫。工具先備份，於遠端單一交易移入 schema3、records、users、requests、audit，保留 ID、密碼雜湊、角色、修訂、刪除標記、原工作簿與操作歷程；完整內容雜湊相同才提交。重複移入相同內容安全略過，目標已有不同內容或較新版本標記時拒絕覆蓋。sessions 不搬移，使用者重新登入。

本次使用 Vercel 受保護的建置環境讀取敏感資料庫金鑰完成搬移，不讀出該金鑰、不提供公開搬移 API。私密建置輸入在工作完成時移除；暫時驗證用敏感環境變數及失敗建置也已清理。正常部署只包含 App 程式，沒有來源資料庫或登入密碼檔。

管理員可以下載完整 JSON 備份。雲端內部更正前備份與正式資料在同一資料庫，不代替另外保存的災難復原備份。資料與工作簿留在受保護的資料庫及維護環境 .data，沒有放入公開程式包。

## 驗收與限制

已做：真實 Turso HTTPS交易、內容核對、重複搬移、後端既有帳號登入與登出、未登入拒絕、CSRF拒絕、兩個歷史日期統計；正常 Vercel Production 部署 Ready。

尚待：正式網址瀏覽器 HTTPS登入、重新部署後公開介面重讀、多人／跨裝置同步、真實 Android／iPhone／iPad 與行動網路、加入主畫面。本版 Docker/Caddy 未重跑。不能把過去版本或模擬服務測試當成這些項目已通過。

## 最後使用哪個檔案

日常直接使用正式網址。維護原始碼使用 GitHub main；離線交付使用 **release/pigledger-1.3.1.zip** 及同名 sha256。舊版本程式包與報告保留，不與新版本同名覆蓋。
