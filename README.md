# 肉豬紀錄管理 App — PigLedger 1.0.0

**正式使用請部署整個專案，開啟 HTTPS 網站。不要直接開 `index.html`，也不要使用手機「檔案預覽」。**

下載交付包 `pigledger-1.0.0.zip` 後解壓縮，以本檔為入口。六頁共用同一 SQLite 持久資料庫和伺服器帳號；手機、平板、電腦透過同一網址使用。繁體中文／越南語切換、角色權限、CSV、完整備份、更正歷程、衝突及重送處理均已實作。沒有自動叫料、配送／採食量預測或相關背景工作。

- [Docker 正式部署步驟](docs/DEPLOY.md)
- [日常操作說明](docs/USER_GUIDE.md)
- [資料模型、更新與保留](docs/DATA.md)
- [測試結果及待驗收項目](docs/TEST_REPORT.md)

## 本機開發

需要 Python 3.12+；應用程式只用 Python 標準函式庫，沒有第三方服務或套件依賴。

```sh
cd /workspace/555
python3 -m app.manage create-admin --username YOUR_ADMIN
python3 -m app.server --host 127.0.0.1 --port 8080
```

管理員密碼在終端機隱藏輸入，至少12字元。沒有預設帳號、密碼或內嵌管理員密鑰。開發時使用本機 HTTP；正式部署使用下方 Docker + Caddy HTTPS。資料預設在 `.data/pigledger.sqlite3`，可用 `--db` 或 `PIGLEDGER_DB` 指定。啟動伺服器不會建立示範豬隻或清空資料。

```sh
./scripts/check.sh
# 以下瀏覽器測試需要 Playwright（測試依賴）及 Chromium：
python3 tests/browser_smoke.py
python3 tests/pwa_test.py
```

正式環境使用 Docker 持久 volume `farm_data`；SQLite 支援單一應用實例的多人交易。請勿以共享網路磁碟承載 SQLite，也不要啟動多個不同 volume 的應用實例當成同一場資料。需要跨區／多實例服務時，應另外規劃資料库服務及迁移。

## 交付內容

`app/` 是完整原始碼；`Dockerfile`、`compose.yaml`、`Caddyfile` 是正式部署入口；`tests/`、`docs/`、`VERSION` 同包提供。範例資料只存在隔離測試，交付包不含農場資料庫或正式密碼。程式包 SHA-256 在同名 `.sha256` 檔中。
