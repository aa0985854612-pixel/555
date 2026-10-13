# PigLedger 1.1.0 — Windows筆電版驗證

2026-10-13。本版新增本機啟動器與官方Python執行環境包。六頁、計算、資料庫 schema2、帳號權限及備份格式沿用原App。雲端開發資料庫在變更前以SQLite Backup API備份；原farmadmin、密碼雜湊及操作紀錄保留。正式程式包不包含這些資料。

## 已實際執行

- **48項Python自動化通過，0失敗／跳過**（Linux/Python3.12執行，合成資料）。原40項計算、交易、權限、重送、備份／還原、刪除墓碑與schema更新，另新增8項筆電啟動測試。
- 筆電啟動：固定Windows使用者資料位置、首次建立管理員與密碼雜湊、重開不重設／不再提示、密碼檢查、並發首次建立僅一名管理員、已有帳號不自動建新管理員、資料庫身份確認、真實launcher子程序的HTTP登入、儲存、重複開啟及停止／重啟後資料仍在。作業系統路径選擇以模擬Windows參數測試；真正啟動子程序使用Linux，沒有冒稱Windows實測。
- **17個Chromium情境通過**：六頁、語言／焦點／閱讀位置、儲存、連按、回應丟失、待送重開、斷線、CSV、衝突及角色切換。使用本版原始碼及合成資料。
- **5項PWA檢查通過**：真實Chromium生命週期，模擬舊0.9.0→1.1.0快取；草稿阻止套用更新，舊快取移除，API不快取，PNG圖示規格。
- 原v1.0.0 Docker／HTTPS測試結果仍見[舊版報告](TEST_REPORT.md)。本版以Windows交付為目標，沒有重新宣稱本版Docker與正式HTTPS網站驗收。

## Windows執行環境與程式包

- 選用Python Software Foundation的 **Python3.14.8 Windows x64 NuGet套件**。CPython官方Windows文件將`python` NuGet包列為官方Python分發方式。
- 由允許的NuGet官方HTTPS來源下載，依官方catalog的SHA-512比對原包，ZIP CRC檢查通過。
- 不變更runtime DLL／EXE內容；保留原NuGet包（含repository signature）、來源JSON及所有解出檔案SHA-256。原始套件與runtime內容逐檔比對一致。沒有停用TLS或修改預期checksum。
- Windows啟動bat使用ASCII、CRLF與完整路徑引號，呼叫隨包Python，不依賴系統Python／Docker。
- ZIP不含`.data`、實際帳號密碼檔或農場SQLite資料庫。資料位置`%LOCALAPPDATA%\PigLedger\data`不會因新版解壓資料夾改變。

## 模擬／未驗收

Windows路径選擇、網路斷線及版本升級資料使用模擬或合成資料。**尚未在真實Windows10/11筆電雙擊bat、執行Python3.14.8 Windows runtime、驗收原生密碼輸入與瀏覽器自動開啟**；目前雲端主機是Linux，無法代表Windows實機。正式Windows結果需由使用者第一次啟動確認。

本版不是公開雲端服務；App只綁定127.0.0.1，資料儲存在使用者筆電。手機／多人遠端與正式HTTPS網址需要另行部署；備份格式可安全移轉，不重新造一套數據。

## 重跑

```sh
./scripts/check.sh
python3 tests/browser_smoke.py
python3 tests/pwa_test.py
```

Windows部署及第一使用步驟見根目錄[WINDOWS_README.txt](../WINDOWS_README.txt)。正式登入密碼由使用者在啟動console隱藏輸入，沒有預設值。
