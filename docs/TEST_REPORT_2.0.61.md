# 2.0.61 — 完整肉豬紀錄表

## 修正問題

肉豬每週紀錄表原本會從統計頁沿用起迄日期，後端再把叫料限制在今天以前，整個未來週期也會在畫面及PDF中留白。因此已經正式登記的未來叫料不會出現在紙本。

本版改為先選棟舍、自動帶出最新批次，可切換舊批次或同批全部棟舍。移除日期輸入及統計頁日期繼承，開啟或換棟舍即產生預覽。使用讀取API的 `all_records=1`，從進場日起列出本批全部已登記資料，延伸到最後一筆已登記日期；進場前的飼料仍照原日期獨立列示，不受舊週表起始設定截斷。

「叫料即到料」啟用時沿用原始叫料與舊到料資料的單一到料視圖，按原ID去重，不新增資料副本。畫面、PDF、列印及CSV全部顯示已登記的未來資料。未登記的預排週欄仍留白。共用桶整批計一次；單棟沒有確認分配時列出原桶量及待確認狀態，不平均分配。14-1/14-2的紙本簡稱仍為14。

全部登記合計包含未來紀錄；目前存欄、育成率、庫存及截至日期統計仍以其原有截至日期計算。開啟中的報表隨原同步流程收到資料異動後重新產生，更正與刪除會反映在新預覽。已下載的PDF或已列印的紙張須重新下載／列印。

## 修改檔案與資料庫

- `app/weekly.py`：完整登記讀取模式、單一飼料紀錄來源、未來資料與當日存欄分開計算；原有指定起迄日期API保留相容。
- `app/static/weekly-report.js`：棟舍優先、最新批次自選、移除日期輸入、自動預覽及資料同步刷新、未來週期有登記即顯示。
- `app/static/feed-receipts.js`：紙本飼料名稱與說明遵循叫料即到料政策，繁體中文／越南語。
- `VERSION`、`app/store.py`、`pyproject.toml`、`Dockerfile`、`app/static/app.js`、`app/static/index.html`、`app/static/sw.js`：2.0.61及快取更新。
- `tests/test_weekly_all_records.py`、`tests/weekly_all_records_browser.py`：完整登記與未來日期回歸測試。
- `tests/feed_dates_browser.py`、`tests/shipment_grouping_browser.py`：依新的無日期、選棟舍流程驗證原飼料格式及出豬合併。
- `README.md`、`docs/USER_GUIDE.md`：操作與日期計算說明。

資料庫結構版本仍為4，沒有新增表、遷移、重建或重寫農場紀錄。沒有觸發實際通知、LINE或付費辨識。

## 測試結果

使用隔離SQLite、既有合成Hrana測試、實際Chromium與HTTP；不登入正式農場或寫入測試資料。

| 驗證 | 結果 |
| --- | --- |
| `sh scripts/check.sh` | 762個單元／整合測試通過，包含新增10個完整週表測試；JavaScript語法檢查通過 |
| `python3 tests/weekly_all_records_browser.py` | 8個情境通過 |
| `python3 tests/feed_dates_browser.py` | 7個情境通過 |
| `python3 tests/shipment_grouping_browser.py` | 6個情境通過 |
| `python3 tests/weekly_full_feed_browser.py` | 5個情境通過 |

本次共26個瀏覽器情境。白板24筆78噸以合成資料依原日期／廠商／實際料桶重現，分配到各自批次後，API核對24個原ID均只出現一次且合計78噸，包含10/26、10/27。13／22棟的同批紙本驗證四筆12噸；單獨13棟驗證10/24四噸及10/26四噸。畫面、PDF實際繪字與CSV逐筆數量相同，沒有第二份到料紀錄。

另驗證完全在未來週期的11/3一筆1.5噸，透過其他裝置寫入的模擬直接刷新開著的報表；更正成1噸及刪除都正確回算。舊統計日期不影響完整週表；更早的進場前飼料保留；未來死亡不提前扣目前存欄，未來到料不提前增加目前庫存。未確認共用桶量保留待確認標示。

320、390、768、1440寬度與中越語介面無水平溢出。保留同日日期只列一次、原始CSV完整日期、同車次出豬合併、190筆飼料跨頁與70筆進場前飼料完整列印。讀者可查報表，登出後API回401。沒有JavaScript錯誤。

產物：`artifacts/weekly-all-records-mobile.png`、`artifacts/weekly-all-records-whiteboard.pdf`、`artifacts/weekly-all-records-results.json`及其他飼料／出豬合成測試PDF。未模擬實體手機、印表機或以正式資料進行測試。

## 部署

沿用原GitHub倉庫與Vercel專案，發布2.0.61。保留 `FEED_ORDERS_ARE_ARRIVALS=1`、原Turso資料庫、正式網域與台灣上午10點提醒。核對原生Git部署READY與提交SHA、網域指向及排程設定；不建立臨時測試部署、不新增正式測試紀錄。服務工作者更新至2.0.61並保留既有裝置通知資料。
