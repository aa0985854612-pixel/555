# 2.0.19 — 歷史叫料可暫不填料別

日期、棟舍／料桶及噸數可先保存；料別允許空字串，非空仍限原三種選項。明確清空廠商時保留空白；未傳廠商的舊客戶端仍使用料桶預設值。選棟自動帶入廠商的功能保留。編輯已有紀錄會保留其料別、廠商和料桶快照。

驗證：

- `sh scripts/check.sh`：480 個單元／整合測試通過、13 個 JavaScript 語法檢查通過；包含 SQLite 和模擬 Turso 的空白料別、空白廠商、修改噸數、既有料別及舊客戶端預設值測試。
- `python3 tests/feed_bins_browser.py`：12 個真實 HTTP／Chromium 情境通過，包含留空料別與廠商後送審儲存、再編輯噸數，原有有料別紀錄保持不變。
- `python3 tests/feed_review_browser.py`：6 個情境通過。
- `python3 tests/feed_orders_browser.py`：13 個情境通過。
- `python3 tests/pwa_test.py`：5 項通過。

瀏覽器使用合成帳號和隔離資料庫，涵蓋手機視窗、語言和字級。未使用客戶密碼，未測實體 iPhone 或實體列印。此套件不包含農場照片、匯入資料或私有維護腳本。
