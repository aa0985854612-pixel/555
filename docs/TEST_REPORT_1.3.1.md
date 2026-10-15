# PigLedger 1.3.1 測試與交付

日期：2026-10-15。修正真實 Turso 拒絕 `PRAGMA user_version=3` 的相容性問題，改用交易內的 `cloud_metadata` 版本標記，仍可讀舊雲端標記；本地 schema3 與原資料不重建。前端、後端、PWA快取與原始碼包版本統一為1.3.1。

## 本版已執行

| 檢查 | 結果 | 真實／模擬及範圍 |
| --- | --- | --- |
| `scripts/check.sh` | 131項通過，0失敗、0跳過；Node語法通過 | 真實執行既有計算、HTTP、TLS、帳號、匯出、舊表與衝突測試；雲端協議使用隔離SQLite的Hrana模擬 |
| 新增相容性回歸 | 3項通過，包含於131項 | 模擬提供者拒絕PRAGMA時仍能搬移、重複執行及讀取；舊雲端標記可讀且普通請求不改schema；較新標記拒絕覆蓋 |
| `tests/pwa_test.py` | 5項通過 | 真實Chromium、模擬舊快取；未存輸入保留，新版啟用清除舊快取，API不快取，圖示存在 |
| 真實Turso資料搬移 | 通過 | 在Vercel建置機使用受保護資料庫金鑰；搬移前備份來源，以完整內容SHA-256核對records、users、requests、audit；相同資料重跑略過 |
| 既有帳號與歷史後端驗證 | 10項檢查通過 | Vercel建置機的loopback HTTP執行真正API handler，連接真實Turso；健康版本、未登入拒絕、原farmadmin登入及Secure/HttpOnly Cookie、session身份、分棟批次、兩個歷史日期統計、CSRF拒絕、登出失效、原始文件內容不變 |
| Vercel普通Production部署 | Ready | 正常App程式，原正式網域已指向1.3.1；不含私密搬移輸入、來源SQLite或登入密碼檔。平台Ready不是公開瀏覽器登入驗收 |

正式網址：<https://555-rho-nine.vercel.app/>。維護環境直接連此網域仍被網路代理拒絕403，所以後端驗證是在Vercel建置機內執行，不能稱為已實測正式HTTPS登入。

## 資料保留與安全

原49筆records、1位使用者、1筆去重requests及50筆audit內容完全相同。保留原帳號ID、密碼雜湊、角色、修訂、原Excel及操作歷程；sessions刻意不搬移。原SQLite、備份及原檔仍在維護環境私密目錄。沒有清庫、重新建立管理員或把未知數補為0。

新增雲端內部 `cloud_metadata`；網站請求僅讀取版本，不自行更新schema。明確搬移仍以單一交易核對後提交，已有不同資料或較新版本則拒絕。測試登入、登出後再次核對原始四表內容未變。

資料庫金鑰由Vercel敏感環境變數提供，未顯示、帶回維護環境或放入程式包。臨時登入驗證機密已從專案設定刪除，包含私密建置輸入的失敗部署已刪除。既有金鑰及帳號沒有重設。

## 仍待驗收

- 正式網址的瀏覽器HTTPS登入、部署後公開頁面重讀及多人跨裝置同步。
- 真正Android、iPhone、iPad、行動網路、加入主畫面與實際離線操作。
- 本版Docker/Caddy重建與Windows實機。
- 本版完整17情境browser_smoke、10情境legacy_browser及官方本地runtime未重跑；過去1.3.0結果保留在舊報告，沒有算入本版通過數。

頭數、育成率、飼料、秤重、ADG、FCR、歷史篩選、重送與伺服器權限的既有自動測試，本版已隨131項重新執行。語言切換與同步保留焦點等完整瀏覽器情境本版未重跑；手機實機、公網、跨裝置仍待驗收，不以模擬測試代替。

## 使用入口

日常使用正式網址；維護部署使用GitHub `aa0985854612-pixel/555` 的 `main`，或 **release/pigledger-1.3.1.zip**。新包保留同一套App原始碼，不包含私人資料、金鑰或登入密碼。操作見 [USER_GUIDE.md](USER_GUIDE.md)，部署與資料保留見 [VERCEL.md](VERCEL.md)。
