# PigLedger 1.2.0 測試與交付結果

2026-10-14。本版新增Windows手機HTTPS啟動器、原表XLSX匯入及來源基準統計，保留六頁與既有功能，沒有預測／自動叫料。

## 真實執行

- 80項Python測試通過，0失敗／跳過。使用Linux／Python3.12、隔離SQLite及合成資料：原計算／帳號／衝突／重送、8項筆電、15項手機啟動／TLS、17項來源匯入測試。
- 手機TLS：實際本機HTTPS反向代理、憑證驗證開啟、Secure/HttpOnly/SameSite cookie、HSTS、Host／Origin／CSRF、未登入與唯讀角色拒絕、相同資料庫及重送去重。Cloudflare連線服務使用模擬，沒有冒稱公開網路實測。
- 啟動生命週期：實際Linux子程序、重複啟動鎖、檢查同一資料庫及版本後才顯示成功、先偵測同資料庫舊版並拒絕直接遷移、SIGTERM正常停止自己的子程序、保留原資料、校驗錯誤不執行connector。
- 原17個Chromium情境通過：六頁、語言／焦點／閱讀位置、連按、回應丟失／重開／斷線、CSV、冲突、角色切換及手機／平板／桌面尺寸。
- 新10個Chromium原表情境通過：預覽不寫入，語言切換保留檔案與輸入，提交後回應丟失可重試、不重複及不假報成功，来源提示、原檔下載逐位元組相同、日齡修正保留未知進場數、唯讀历史篩選、新舊基準不重扣、未知歷史日期顯示—、手機版面與無JS錯誤。
- 5項Chromium PWA檢查通過，模擬旧0.9.0→1.2.0版本：未存草稿阻止套用、快取移除、API不快取、PNG圖示及生命週期。
- 使用者上傳的真實工作簿另在隔離資料庫實際核對：原始位元組／SHA-256保留、各類異動及存欄合計一致、每棟獨立ID、合併批次首次日期計齡、已出完棟結束、備份還原一致。確認後才匯入開發資料庫；原帳號ID、角色、密碼雜湊與歷程保留。真實農場數字與原表僅在私密來源及備份，不刊入本公開報告或程式包。

- 8個Docker／Caddy情境在本版實際執行：隔離測試volume，連接埠只綁loopback，HTTPS憑證驗證開啟、登入、Secure cookie／HSTS、FCR、schema3備份、重啟保留資料。測試後僅移除本次測試project的容器及volume，沒有操作農場資料。

## 套件与資料保留

SQLite schema2→3先以Backup API備份，不清空／重建；保留原records、users、audit並支持未知單棟進場分母及不可重复扣除的來源基準。完整JSON備份schema3含原表，接受schema1／2；同ID／同SHA去重，較新或衝突不覆蓋現有更正。

Windows runtime為PSF Python3.14.8 NuGet，已對官方catalog SHA-512；cloudflared2026.10.0官方Windows SHA-256與winget manifest相同。原包、license、來源metadata及逐檔hash隨包保留；檔案不修改、不停用TLS、connector不自動更新。ZIP排除實際資料庫、密碼檔、工作簿與私密匯入資料。

## 模擬與未驗收

Windows路徑、Cloudflare lifecycle、斷線與舊快取情境含模擬；實際服務／SQLite／子程序／Chromium／TLS均在Linux執行。尚未在Windows10/11實機雙擊BAT或執行Windows runtime，未驗收實體Android/iPhone/iPad加入主畫面及行動網路。

本雲端網路對api.trycloudflare.com與使用者提供Vercel網站回覆403，沒有繞過限制。棟舍概略數改採使用者直接提供並核對原表；Quick Tunnel真正公開URL需由Windows筆電啟動後驗證，不交付不存在的正式網址。這是臨時連線，不具固定網域／全天候保證。

來源只足以支持特定盤點日或截至日的累計。單棟進場分母、未指定棟別的歷史事件、運送與死亡歸類先後、缺樣本數的均重等保留未知／唯讀來源，不能宣稱全部歷史日期與FCR均可精確計算。新紀錄從來源基準次日開始，管理員盤點調整及日齡更正有稽核。

## 重跑

```sh
./scripts/check.sh
python3 tests/browser_smoke.py
python3 tests/legacy_browser.py
python3 tests/pwa_test.py
```

日常及手機操作見WINDOWS_README.txt，來源移入見EXCEL_IMPORT.md。歷史報告保留，不把舊版測試當成本版正式網站驗收。
