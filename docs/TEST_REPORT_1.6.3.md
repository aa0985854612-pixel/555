# PigLedger 1.6.3 手機安裝圖示測試

本次修正使用者所指的「安裝並建立捷徑」圖示。依原Q版插畫，以圖像生成工具製作單一豬隻的方形主圖，再輸出Android 192／512 PNG、Android 512 maskable及iPhone 180 PNG。maskable保留中央安全邊距，讓圓形裁切保留鼻子、眼睛及耳朵。圖示沒有文字，名稱以manifest顯示「嘉得肉豬紀錄」。原Q版登入封面保留。

新圖示使用明確1.6.3檔名，manifest網址與SW快取同版更新；PWA id、start_url、scope及正式網域保持。原icon PNG／SVG也更新相容圖片。Apple touch、favicon及頁首小圖使用新版。manifest、PNG、SVG及WebP明確指定MIME，避免部署平台差異。

## 本地真實執行與合成／隔離環境

- `sh scripts/check.sh`：186項測試通過，0失敗、0略過；4份JavaScript語法檢查通過。新增無系統MIME資料庫時，manifest與安裝PNG仍回傳正確格式的回歸案例。
- `python3 tests/install_icon_browser.py`：7組真實Chromium檢查通過。以獨立持久瀏覽器設定檔執行，沒有沿用使用者瀏覽器或正式帳密。
- 確認版本化manifest、App名稱及固定身分；Android any及maskable的實際PNG尺寸與MIME；iPhone 180及favicon位置；Chromium DevTools實際解析manifest，正常瀏覽模式的installabilityErrors為空；新圖示可由離線快取讀取；320／390／768／1440px頁首無水平溢出；圓角與圓形裁切預覽沒有JavaScript錯誤。
- 初次使用無痕測試環境時，Chromium回報in-incognito，已改用隔離的正常持久設定檔完成檢查，未忽略該限制或將無痕安裝列為通過。
- `python3 tests/pwa_test.py`：5項舊／新SW生命週期檢查通過，未保存草稿阻擋強制更新、API不快取的保護繼續保留。
- 合計12組／項瀏覽器檢查通過。預覽是瀏覽器呈現，不是Android桌面或iPhone主畫面實機截圖。

## 正式資料及部署

修改前已核對正式結構並在原Turso建立持久備份。本版不更新農場紀錄、批次數字、帳號或密碼，不執行資料庫結構變更；沿用schema4、原GitHub main、Vercel專案與HTTPS網址。

正式部署後核對HTTP首頁／health／manifest、新PNG的MIME、尺寸與檔案校驗值、SW引用及資料指紋，細節保存在私密維護紀錄。網站資源更新與裝置既有圖示更新是兩件事；已安裝圖示由手機系統更新，必要時完成送出後移除舊捷徑並重新加入。

尚未驗收：實體Android安裝、WebAPK與啟動器的圖示更新時間、iPhone主畫面加入與圖示更新、使用者目前密碼的正式HTTPS登入。沒有宣稱這些測試通過，沒有為測試重設帳號。
