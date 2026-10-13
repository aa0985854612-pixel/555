# 肉豬紀錄管理 App — PigLedger 1.1.0

**只有 Windows 筆電？下載筆電版，全部解壓縮後雙擊 `START_WINDOWS.bat`。**

- **[下載 Windows 筆電版 v1.1.0](https://github.com/aa0985854612-pixel/555/raw/refs/heads/main/release/pigledger-windows-1.1.0.zip)**（內附 Python，不必安裝 Docker／另租主機）
- [Windows 操作說明](WINDOWS_README.txt)
- [本版測試及資料保留](docs/TEST_REPORT_1.1.0.md)
- [完整原始碼包](https://github.com/aa0985854612-pixel/555/raw/refs/heads/main/release/pigledger-1.1.0.zip)

首次啟動在黑色視窗設定帳號與至少12字元密碼，瀏覽器自動開啟後登入。密碼輸入不顯示字元是正常的。再次開啟沿用帳號與資料。使用時保留啟動視窗，按Ctrl+C可停止。

Windows 資料固定放在 `%LOCALAPPDATA%\PigLedger\data\pigledger.sqlite3`，與解壓的版本資料夾分開。更新前備份、關掉舊視窗，再雙擊新版。之前雲端開發環境的帳號不會跟程式包搬到筆電；下載包沒有正式密碼或農場資料。備份可匯入同一 App 的雲端部署。

這是同一套六頁 App、資料模型及權限。Windows 版本僅新增啟動器，沒有另寫一套不相通的計算。支援繁體中文／越南語，豬隻異動、到料與耗料分開、加權均重、ADG、FCR、CSV、備份、更正歷程及重送／衝突處理。沒有自動叫料、配送或採食量預測。

## 雲端部署

Docker 原有方式保留，參考[部署說明](docs/DEPLOY.md)。正式使用手機／多人遠端操作，需部署到HTTPS網站；不要開HTML檔案預覽。單機 Windows 版僅提供筆電自己的 loopback 連線，不提供公開網址。

- [日常登記指南](docs/USER_GUIDE.md)
- [資料模型及備份](docs/DATA.md)
- [舊版1.0.0測試報告](docs/TEST_REPORT.md)

## 開發驗證

共用應用使用 Python 3.12+ 標準函式庫，無第三方應用依賴。

```sh
./scripts/check.sh
python3 tests/browser_smoke.py
python3 tests/pwa_test.py
```

本機啟動器可在已有Python環境執行 `python3 -m app.desktop`；啟動器會依作業系統決定資料位置。測試用 `--data-dir`指定隔離暫存位置，不寫入正式資料。Linux/macOS可用啟動器，但本次交付的內附執行環境ZIP為Windows x64。

Windows runtime 來源為 CPython 官方 Windows 文件推薦的 PSF NuGet `python` 套件。打包時以官方catalog SHA-512核對完整原包，保留 NuGet 原包及逐檔校驗資料，不修改DLL。原生Windows雙擊操作尚未在本雲端Linux機驗收，詳見本版報告。

重建Windows交付包：

```sh
python3 scripts/fetch_windows_runtime.py
python3 scripts/package.py
python3 scripts/package_windows.py
```

打包腳本會核對已下載的PSF原包SHA-512，拒絕不一致的檔案；不會把使用者資料夾放進程式包。
