# 肉豬紀錄管理 App — PigLedger 1.3.1

**建議部署至 Vercel，手機與電腦共用固定 HTTPS 網址；筆電不必保持開機。**

- [在 Vercel 匯入此專案](https://vercel.com/new/import?s=https%3A%2F%2Fgithub.com%2Faa0985854612-pixel%2F555)
- [Vercel 設定與原資料移入](docs/VERCEL.md)
- [本版測試結果與部署狀態](docs/TEST_REPORT_1.3.1.md)
- [完整 Vercel／Docker 原始碼包 v1.3.1](https://github.com/aa0985854612-pixel/555/raw/refs/heads/main/release/pigledger-1.3.1.zip)

Vercel 版使用持久 Turso/libSQL 資料庫，沿用同一套頁面、批次、統計與伺服器權限。原 SQLite 移入工具先備份，再完整保留帳號密碼雜湊、原始 Excel、紀錄 ID、修訂、操作歷程與去重紀錄；重複移入不新增，已有不同資料時拒絕覆蓋。新網址需重新登入，不重設密碼。

**正式網址：[555-rho-nine.vercel.app](https://555-rho-nine.vercel.app/)。2026-10-15，1.3.1 已在 Vercel 部署為 Ready，原資料與帳號已私密搬入 Turso。** 真實 Turso 的完整內容核對、重複搬移及既有帳號後端登入已通過。維護環境到正式網站的直接連線仍被網路代理403阻擋，未宣稱正式 HTTPS 瀏覽器登入或實體手機已驗收。詳細範圍見本版測試報告。

日常使用：用手機 Safari／Chrome 開上述網址，以原帳號登入；每日登記豬隻異動，到料／實際耗料及秤重數字分別到對應頁面。加入主畫面後可直接開啟；筆電可以關機。[簡短操作說明](docs/USER_GUIDE.md)。`farmadmin` 密碼沿用原設定，程式包與 GitHub 不包含密碼或私人資料。

1.3.1 修正實際 Turso 拒絕寫入 `PRAGMA user_version` 的相容性問題：雲端版本標記改存 `cloud_metadata`，與搬移資料同一交易提交；讀取時仍相容舊雲端版本標記。本地 SQLite 的 schema3、原始資料及帳號不重建。

原筆電版仍可使用：

- [下載 Windows／手機版 v1.2.1](https://github.com/aa0985854612-pixel/555/raw/refs/heads/main/release/pigledger-windows-1.2.1.zip)，全部解壓縮後啟動，內附官方 Python 與 Cloudflare 連線程式。
- [Windows／手機操作說明](WINDOWS_README.txt)
- [Excel 移入說明](docs/EXCEL_IMPORT.md)
- [筆電版 v1.2.1 測試結果與限制](docs/TEST_REPORT_1.2.1.md)

首次啟動設定管理員與至少12字元密碼；再次啟動沿用帳號與資料。資料固定存在 %LOCALAPPDATA%\PigLedger\data\pigledger.sqlite3，換版本資料夾不重建。schema2→3 自動先備份，保留帳號、原始紀錄與歷程。程式包不包含使用者工作簿、農場資料或密碼。

手机模式取得臨時 HTTPS 網址，Safari／Chrome 可用行動網路登入。啟動器檢查公開健康狀態成功才顯示可用網址。筆電必須開機、連網、不睡眠；Ctrl+C 只停止自己的服務。Cloudflare Quick Tunnel 沒有全天候服務保證，重啟可能換網址。固定正式網址使用[雲端部署](docs/DEPLOY.md)。本雲端網路阻擋 Cloudflare API，Windows雙擊及真正外出手機連線仍待實機驗收。

六頁共用一份 SQLite：每日登記、週期統計、歷史紀錄、飼料紀錄、秤重紀錄、設定。繁體中文／越南語、角色、修訂衝突、重送去重、CSV、備份與計算沿用共用程式。沒有自動叫料、配送或採食量預測。

設定內可預覽與匯入「肉豬各周存欄頭數」原始 XLSX。填實際盤點日與概略分棟數，按原表總數核對。來源累計不再次扣除；分棟分配標示暫定，缺各棟進場分母／死亡時育成率未知。原檔、舊表、公式與備註保存於私密備份。來源歷史／CSV標示唯讀及儲存格；缺日期或样本頭數的內容不變成假異動或假秤重。合併批次用首次進場日計齡，保留原始明細。

## 開發與重建

App 使用 Python3.12+ 標準函式庫，XLSX解析不需 openpyxl。瀏覽器測試需 Playwright／Chromium，TLS測試需 OpenSSL。

```sh
./scripts/check.sh
python3 tests/browser_smoke.py
python3 tests/legacy_browser.py
python3 tests/pwa_test.py
```

```sh
python3 scripts/fetch_windows_runtime.py
python3 scripts/fetch_cloudflared.py --platform windows-amd64
python3 scripts/package.py
python3 scripts/package_windows.py
```

PSF NuGet Python3.14.8 原包以官方catalog SHA-512核對，保留原包、signature及逐檔SHA-256。cloudflared2026.10.0 以官方release SHA-256核對，與winget manifest相符，啟動前再驗證；二進位不修改、不停用TLS、不自動升級connector，Apache授權隨包保存。

Linux開發可用 python3 -m app.desktop --data-dir /tmp/isolated-farm。手機啟動器額外指定已驗證的Linux connector。測試使用隔離資料，不更改正式農場。歷史版本程式包與報告保留。
