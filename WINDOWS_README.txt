肉豬紀錄管理 App — Windows 筆電版 v1.1.0

【只要做這些】
1. 下載 pigledger-windows-1.1.0.zip。
2. 在 ZIP 上按右鍵 →「全部解壓縮」。不要直接在 ZIP 裡執行。
3. 進入解壓後的資料夾，雙擊 START_WINDOWS.bat。
4. 第一次會出現黑色視窗：
   Username [farmadmin]: 按 Enter 使用 farmadmin，或填你的帳號。
   Choose a password: 自己設定至少12字元密碼。
   Enter the same password again: 再輸入一次相同密碼。
   輸入密碼時不會顯示字元，這是正常的。
5. 瀏覽器會自動開啟 App。輸入剛才設定的帳號密碼登入。
6. 使用時保留黑色視窗開著；瀏覽器關掉不會停掉 App。
   要結束可在黑色視窗按 Ctrl+C，再關掉視窗。

【每天使用】
再次雙擊 START_WINDOWS.bat 即可，不會再問你建立帳號。
第一次登入後到「設定」建立棟舍及批次。
日常填「每日登記」、「飼料紀錄」及「秤重紀錄」。
計算在「週期統計」查看，原始紀錄在「歷史紀錄」查詢。
沒有足夠資料時显示 — 或資料不足，不用補假數字。

【瀏覽器沒有自動開啟】
看黑色視窗內「PigLedger ... is ready:」後的網址，
複製到 Chrome 或 Edge。通常為 http://127.0.0.1:8080/。
這個網址只適用於你自己正在執行此 App 的 Windows 筆電，
不是 ChatGPT 雲端環境預覽，也不是公開雲端網址。

【資料與更新】
資料固定存到 Windows 使用者資料夾：
%LOCALAPPDATA%\PigLedger\data\pigledger.sqlite3
例：C:\Users\你的名稱\AppData\Local\PigLedger\data\pigledger.sqlite3
換版本資料夾仍沿用這份資料，不會重建或清空。
更新前到「設定 → 下載完整備份 JSON」。
先關掉舊版啟動視窗，再解壓新版、雙擊新版 START_WINDOWS.bat。
不要刪除上面的 PigLedger 使用者資料夾。

【帳號】
之前在 ChatGPT 開發環境建立的 farmadmin 不會自動搬到筆電。
筆電第一次啟動時請自行建立自己的帳號密碼。
這個下載包没有正式帳號、預設密碼或農場資料庫。

【這版的範圍】
適用 Windows 10/11 64位元（Intel/AMD x64）。
內附 Python Software Foundation 發布的 Python 3.14.8 Windows 執行環境。
下載與官方 NuGet SHA-512 校驗已核對，保留原包與來源資料。
不必另外安裝 Python 或 Docker。
這是單台筆電本機使用，不是多人遠端雲端服務；只有本機可連線。
可以沒有網路仍在筆電登記；要備份並確認儲存成功。
未來部署成雲端網站時，可用完整備份匯入搬移資料。

【測試】
已在 Linux 雲端機實跑共用程式的計算、資料庫、啟動、登入和重啟測試，
並核對 Windows 執行環境與 ZIP 完整性。
尚未在真實 Windows 筆電雙擊驗收；若有錯誤，保留黑色視窗並截圖給我。
請勿把密碼貼在聊天中。
