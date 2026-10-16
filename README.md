# 肉豬紀錄管理 App — PigLedger 1.7.2

**[開啟正式網站：555-rho-nine.vercel.app](https://555-rho-nine.vercel.app/)**。沿用你目前的帳號、密碼、Vercel專案及Turso資料庫。

- [完整原始碼／Docker／Vercel程式包 v1.7.2](https://github.com/aa0985854612-pixel/555/raw/refs/heads/main/release/pigledger-1.7.2.zip)
- [簡短操作說明](docs/USER_GUIDE.md)／[部署說明](docs/VERCEL.md)
- [1.7.2測試報告與驗收限制](docs/TEST_REPORT_1.7.2.md)

本版修正手機日期欄位擠壓：日期獨占一列，類型與頭數並排、批號加寬，統一原生輸入／選單顯示並加入iPhone安全距離。保留Aa字級、繁中／越南語、原六頁與資料。Chromium觸控模擬通過；WebKit官方下載受環境網域限制，Safari／iPhone實機仍待驗收，詳見測試報告。

「全場總覽」每張批號卡片仍顯示**整批育成率**，納入同批全部棟舍（含已出清），用可靠分母與累計死亡合計計算。點百分比可查看日期、涵蓋棟舍、分母、死亡及公式；單棟未知不影響已有可靠來源的整批計算，缺整批依據仍顯示—。

保留設定按批次分組：同批各棟集中在一張可展開的卡片，支援搜尋批次／棟舍與飼養狀態篩選。選一棟後直接在該批次內編輯入場頭數、均重及日期，每棟分開保存；未儲存時不會被另一棟覆蓋。其他設定可展開查看。

每日登記仍是預設頁面，新增「全場總覽」切換，收起輸入表單後集中查看各棟存欄、截至今日累計死亡與育成率。點棟舍帶入正確單棟批次回到登記；未知分母保持—及待補原因。手機查詢條件使用較精簡雙欄，維持可調字體、繁中／越南語及六頁功能。

保留新設／更改／重設密碼為4～8位純數字（0–9），保留開頭的0。既有密碼、帳號及登入相容性保留，沒有自動重設任何帳號。到「設定→修改自己的密碼」輸入目前密碼及新的數字密碼；管理員可管理他人帳號。

保留安裝到手機主畫面的圖示更新為嘉得Q版豬，名稱為「嘉得肉豬紀錄」。Android一般圖示／圓形裁切圖示、iPhone主畫面圖示及瀏覽器圖示均使用同一隻Q版豬，換用版本化檔名避開舊圖示快取，原App識別與網址保持。

已安裝的舊圖示由手機系統決定更新時間。若仍顯示舊圖：先完成手上登記及套用網站更新，再移除手機上的舊App／捷徑，從Chrome或Safari重新開正式網址並加入主畫面；不要清除網站資料。正式雲端紀錄保留，重新安裝可能需再次登入。原Q版登入封面保留。

保留右上角「Aa」字體選單：小／中／大，自動記住這台裝置的選擇，登入前後及所有角色皆可使用。切換不重載頁面、不送出農場資料，也不清空正在輸入的內容。重點數字、標題、一般欄位及日期備註分層呈現；大字手機表單改為單欄，保持容易輸入。

保留管理員更正單棟來源批次入場頭數的功能：設定→批次→編輯，填新頭數與更正原因，核對差額後儲存。同步重算存欄與育成率，原始Excel及操作前後值保留；不確定數量時先取消。多棟來源分配仍須對上合計。

沿用深藍、米白及灰色，放大字體；首頁每個飼養中批次顯示可靠單棟育成率。週期統計以期間死亡為主，批次名稱連同棟舍顯示，點死亡數字可查明細；零死亡的其他批次可展開查看。

秤重頁採紙本作業方式：日期與棟舍／批次→各欄（頭部／中部／尾部、欄號）→各隻重量或頭數＋總重量。預設6格，可增減，空白不算0，合計按實際樣本加權。多欄整次原子儲存、失敗不留半份；同日多次分開編號，保留單筆快速登記與更正。

管理員可在異動、飼料、秤重及來源明細旁按「刪除／作廢」，先核對影響並填原因。原值與操作歷程保留，來源更正採獨立識別，不刪整份Excel，重匯不復活；無法可靠調整基準存欄時先補資料。編輯人員不能自行取得刪除權，唯讀不提供寫入功能。

日常手機Safari／Chrome開正式HTTPS網址，加入主畫面；每人使用自己的帳號。原管理員於設定管理帳號，私下發送一次性設定密碼連結。原始Excel、農場資料、密碼、金鑰及備份不在GitHub或程式包。

本版為介面更新，沿用schema4及既有秤重、來源作廢、權限與衝突驗證，沒有資料遷移或重建資料庫。純程式推送main會自動觸發Vercel部署；Excel更新仍先預覽核對再匯入。Vercel Ready與真實後端測試不等於實體手機或公開HTTPS全流程已驗收，詳見報告。

原筆電版仍可使用：

- [下載 Windows／手機版 v1.2.1](https://github.com/aa0985854612-pixel/555/raw/refs/heads/main/release/pigledger-windows-1.2.1.zip)，全部解壓縮後啟動，內附官方 Python 與 Cloudflare 連線程式。
- [Windows／手機操作說明](WINDOWS_README.txt)
- [Excel 移入說明](docs/EXCEL_IMPORT.md)
- [筆電版 v1.2.1 測試結果與限制](docs/TEST_REPORT_1.2.1.md)

首次啟動設定管理員與4～8位純數字密碼；再次啟動沿用帳號與資料。資料固定存在 %LOCALAPPDATA%\PigLedger\data\pigledger.sqlite3，換版本資料夾不重建。本地舊 schema→4 自動先備份，保留帳號、原始紀錄與歷程。程式包不包含使用者工作簿、農場資料或密碼。

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
python3 tests/upgrade_browser.py
python3 tests/redesign_browser.py
python3 tests/entry_correction_browser.py
python3 tests/appearance_browser.py
python3 tests/install_icon_browser.py
```

```sh
python3 scripts/fetch_windows_runtime.py
python3 scripts/fetch_cloudflared.py --platform windows-amd64
python3 scripts/package.py
python3 scripts/package_windows.py
```

PSF NuGet Python3.14.8 原包以官方catalog SHA-512核對，保留原包、signature及逐檔SHA-256。cloudflared2026.10.0 以官方release SHA-256核對，與winget manifest相符，啟動前再驗證；二進位不修改、不停用TLS、不自動升級connector，Apache授權隨包保存。

Linux開發可用 python3 -m app.desktop --data-dir /tmp/isolated-farm。手機啟動器額外指定已驗證的Linux connector。測試使用隔離資料，不更改正式農場。歷史版本程式包與報告保留。
