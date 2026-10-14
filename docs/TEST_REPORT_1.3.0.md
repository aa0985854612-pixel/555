# PigLedger 1.3.0 測試與交付狀態

本版新增 Vercel Python 入口與持久 Turso/libSQL HTTP adapter；原六頁、SQLite 筆電／Docker 模式及計算沿用。**沒有已完成驗證的正式網站網址。** 缺 Vercel 授權、Turso 連線及環境網路存取。下面分開記錄本地真實執行、模擬服務與尚未驗收的項目。

後續進度（2026-10-15）：使用者截圖顯示 `555-rho-nine.vercel.app` 已部署，登入頁顯示「雲端資料庫尚未連接」。此為使用者畫面觀察，不新增任何公網、Turso或正式資料移入通過項目。提供的Vercel Marketplace Turso連結404，已在最新部署說明改用Turso官網；v1.3.0既有程式包與測試結果保持原發布內容。

## 已實際執行

| 檢查 | 結果 | 資料與範圍 |
| --- | --- | --- |
| `scripts/check.sh` | 128 項通過、0失敗、0跳過；Node語法檢查通過 | Linux Python3.12，81項既有檢查＋47項雲端模式檢查；雲端服務使用模擬 Hrana＋隔離 SQLite |
| `tests/browser_smoke.py` | 17情境通過 | 真實 Chromium，本地 HTTP，合成農場資料：儲存、權限、重複點擊、已提交但回應遺失、斷線、衝突、語言／焦點／手機寬度 |
| `tests/legacy_browser.py` | 10情境通過 | 真實 Chromium，合成 XLSX：預覽不寫入、語言保留檔案、重送去重、原檔下載、年齡更正、歷史篩選、基準日及不完整日期 |
| `tests/pwa_test.py` | 5檢查通過 | 真實 Chromium、模擬舊版本快取：未存輸入阻止更新，新快取清舊快取，API不缓存，安裝圖示 |
| 官方 `@vercel/python@25.1.0` 建置 | 通過，Python3.12 function包 | 真實本地建置，使用 Vercel CLI64.1.0 套件；入口與前端存在，私人資料及release包排除。不是正式部署 |
| 官方 `vercel-runtime==0.23.2` | 7檢查通過 | 真實官方執行器本地執行；資料庫使用合成資料／Hrana模擬。驗證 handler載入、靜態路徑及query、健康檢查、Secure登入Cookie、跨invocation登入、唯讀禁止備份、缺token完整503 |
| 私密原資料移入演練 | 完整內容與統計一致，重複移入略過 | 實際49records、1user、1request、50audit；移入本地Hrana模擬庫。帳號ID／雜湊／角色、原Excel、修訂及歷程逐內容核對，原庫不清除、不重設帳號；先建立SQLite備份 |

雲端模擬驗證包含：相同去重鍵並行只一筆、多人更正衝突、容量限制、交易中途constraint失敗不提交部分內容、COMMIT回應遺失後安全重送、不同function instance共用登入嘗試限制、冷啟動保留帳號與資料、未設定資料庫回503且不使用暫存SQLite、token不轉送到不受信任網域。

官方執行器檢查曾找到未配置資料庫時回應被中斷的問題，已修正並實測完整503。測試程式、建置與執行器結果位於原始碼及忽略Git的artifacts；不包含正式token或私人農場檔案。

## 計算驗收對照

| 使用者要求 | 本地／模擬結果 |
| --- | --- |
| 1000進場、出150、淘汰20、死5 | 剩825、合計出170、育成99.5% |
| 新舊批次分開、截至日期不計後來異動 | 通過 |
| 2噸＝2000kg，到料不當耗料 | 通過 |
| 共同到料分配、用量重疊不重複計 | 通過 |
| 100kg/2隻＋240kg/4隻 | 加權56.67kg |
| 14天50→61.2kg | ADG0.80kg/隻/日 |
| 100隻增10kg、用料2500kg | 估計FCR2.50 |
| 異動缺重量、缺實耗、增重≤0 | 不生成正常FCR |
| 日期／棟／批／類型與CSV一致 | 本地HTTP通過 |
| 保存／語言／同步保留操作 | 真實Chromium通過 |
| 重複點擊／斷線／多人衝突 | 本地HTTP／雲端模擬通過 |
| 登入與伺服器唯讀限制 | 本地HTTP／官方runtime通過 |
| 手機版面、PWA更新 | Chromium視窗與快取通過，實機未驗收 |

## 原資料保留

維持schema3；本地資料庫結構不重建。雲端另加 `cloud_backups` 和 `cloud_login_attempts`，由私密移入工具明確初始化，網站請求不自動改schema。實際原庫、原工作簿、管理員及私密備份留在 `.data/`，沒有進GitHub、程式包或公開網站靜態檔案。移入不搬Cookie，新网址需重新登入。

保留Excel完整總数：進場9371，10/14剩7817、正常出1324、淘汰37、死亡193；合計出1361，育成97.94%。10/12總剩8014。分棟數是經使用者授權的小幅核對分配，仍標示暫定；20棟使用更正輸入388，不使用錯誤288。已結束21棟保留批次與來源資料。缺各棟原進場分母，不編造各棟育成率。

## 尚未驗收

- 真實Turso HTTPS交易、平台連線baton／replica行為與額度。
- Vercel公網Production部署、網址、重新部署持久性、跨裝置同步。
- 原Vercel帳號的實際專案／環境變數權限。
- 新增Vercel／Turso網路與金鑰需求的環境設定被ASB拒絕（只回報需檢查requirements與allowed_domains），尚未保存／套用；1.3.0開發啟動說明已另行保存。
- 原生Windows執行、真實Android／iPhone／iPad、行動網路與加入主畫面。
- 本版Docker/Caddy重建未重跑；1.2.1有8項真實隔離HTTPS檢查，不能算作1.3.0正式部署通過。

## 使用檔案

最終Vercel交付是 GitHub `aa0985854612-pixel/555` 的 `main`，或 **release/pigledger-1.3.0.zip**。依 [VERCEL.md](VERCEL.md) 部署、私密移入並完成正式驗證後，手機直接使用Production HTTPS網址。ZIP是部署原始碼包，不是手機登入連結。
