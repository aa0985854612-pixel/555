# 2.1.0 · 六頁共用 UI／UX 更新驗收

日期：2026-11-02。直接修改原專案與既有六頁；不重建App，不建立新資料庫。舊版對照與設計理由見[設計規範](DESIGN_SYSTEM.md)。

## 實際變更

- `app/static/design-system.css`：共用色彩、文字、間距、按鈕、輸入、清單、統計、視窗、登入與設定；桌面側欄／平板／手機底部導覽、觸控尺寸、安全區及減少動態效果。只套用螢幕，保護原A4與列印。
- `app/static/workspace-ui.js`：沿用原DOM與事件的共同元件。日期移至三類登記表單的標題旁；桌面登記／核對並排，秤重輸入優先；六格SVG導覽、目前頁與鍵盤焦點、原生驗證、寫入進度；原資料清單增加搜尋、排序、分頁、手機欄位標籤，保留原筆更正／刪除及原匯出流程。
- `app/static/index.html`：載入共用CSS與JS；新JS在最後呼叫boot的`feed-bulk.js`前載入。既有模組、頁面與表單保留。
- `manifest.webmanifest`／`sw.js`：更新主題色與2.1.0快取，新增兩個共用資源；PWA識別、網址、scope、圖示、獨立模式、通知處理及更新確認流程保留。
- `tests/ui_fixture.py`／`tests/workspace_ui_browser.py`：隔離示範農場與跨版面、清單互動、權限、寫入重試及雙裝置雲端協定測試。
- `scripts/check.sh`：納入新JS語法驗證；版本標記、設計／操作文件與合成畫面對照同步更新。

## 資料庫與後端

schema維持 **4**，沒有新增或修改欄位，沒有資料遷移，沒有API或正式資料寫入。`app/store.py`及`app/static/app.js`只有版本標記變更；原資料存取、公式、權限、衝突驗證、交易、通知及各舊模組不變。

叫料即到料、共用桶按涵蓋棟舍平均分配、人工已確認分量優先、未來日期不提前影響現況、清空批次歷史、相同車次分組、最新料別、原A4單頁與無CSV規則全部沿用。

## 實際測試

`sh scripts/check.sh`：**814個單元／整合測試通過**，耗時101.904秒；後續完成前端細節後，另跑全部JS語法檢查與`git diff --check`，全部通過。後端沒有再次修改。

| Chromium瀏覽器測試 | 通過情境 |
| --- | ---: |
| `workspace_ui_browser.py` | 10 |
| `outgoing_preview_browser.py` | 10 |
| `feed_bulk_browser.py` | 7 |
| `feed_memory_browser.py` | 8 |
| `feed_drafts_browser.py` | 8 |
| `batch_manager_browser.py` | 8 |
| `daily_review_browser.py` | 9 |
| `paper_current_farm_browser.py` | 10 |
| `weekly_note_fill_browser.py` | 4 |
| `weighing_report_browser.py` | 9 |
| `password_browser.py` | 6 |
| **合計** | **89** |

新介面測試另外逐一檢查 **180組**：320／390／768／1024／1440px × 繁中／越南文 × 小／中／大字 × 六頁。均無整頁橫向溢出，全部六個導覽入口可見；原三個日期控制項保持在原生表單內。

清單實測超過25筆資料的上下頁、搜尋後跨裝置刷新保留焦點、空結果、全部筆數、數字正反排序及復原原順序。小數與公斤／噸混合單位按實際數量比較；中越語不同小數／千分位格式均測試。CSV仍匯出原查詢完整結果，不受畫面分頁截斷。原始記錄與帳號值比對未被清單操作修改。

真實HTTP使用隔離的SQLite與`CloudStore`＋Hrana模擬服務：出豬已提交後刻意中斷回應，同鍵重試只扣一次，另一裝置刷新取得相同存欄；唯讀UI禁用且伺服器403拒絕越權。未儲存的數量、棟批、地點及焦點經語言／背景刷新後保留。新樣式與程式已進入Service Worker預快取，原PWA身份不變。登入、一次性開通及密碼修改回歸通過。

A4實際下載與瀏覽器列印均一頁；各棟死亡框、備註用滿高度、出豬逐次數字、共用料桶平均分配、清空／結束紀錄、繁中／越南文及唯讀均通過。沒有修改`weekly-pdf.js`或原報表計算。

## 部署與操作

沿用原GitHub main與原Vercel專案的原生Git部署，版本 **2.1.0**。正式入口仍為 https://555-rho-nine.vercel.app/ 。同一提交須達到READY，再核對原三個正式別名、`FEED_ORDERS_ARE_ARRIVALS=1`、`FEED_AUTO_ALLOCATION=equal`及`0 2 * * *`台灣10:00提醒。私人部署驗收收據保存在`.data/workspace-design/acceptance.json`，不放進公開原始碼。

部署不需要新增環境變數或重建資料庫。完整原始碼包由`python3 scripts/package.py`產生`release/pigledger-2.1.0.zip`；包內不含資料庫、憑證或`.data`。既有裝置看到更新提示後，完成手上登記再按「套用更新」，或儲存後重新開啟網站；不需清除網站資料。

驗證範圍為真實Chromium／HTTP／隔離合成資料及Hrana協定模擬，已檢視六頁手機與桌面畫面；不是正式農場資料的登入寫入測試，也不是實體Safari、Android或安裝後PWA的硬體驗收。沒有發送真實通知，沒有更動帳號、通知金鑰或農場資料。

發布管理API已確認原專案部署READY、提交SHA與正式別名一致，分料及提醒政策不變。本執行環境直接連線正式網域時，被網路代理拒絕建立HTTPS隧道（403）；因此公開網址健康檢查及正式網站端到端登入未能由此環境完成，不將部署READY視為公開HTTPS全流程通過。
