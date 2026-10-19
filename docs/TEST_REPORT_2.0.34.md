# 2.0.34 驗證紀錄

六、日於行事曆畫面、JPEG 與 A4 PDF 使用淡紅底，日期和星期使用深紅字。

- `sh scripts/check.sh`：556 個單元／整合測試、18 個 JavaScript 語法檢查通過。
- `python3 tests/calendar_presentation_browser.py`：6 項瀏覽器檢查通過，涵蓋文字、每日工作分組、手機排版、原始紀錄保留和單頁 A4 匯出。
- 正式資料本週工作表已重新產生並目視確認六、日標色，PDF 為單張 A4；圖片為 1786×2526 JPEG，使用 PDF 相同的圖像資料。

僅變更呈現方式，無資料表結構或工作紀錄變更。
