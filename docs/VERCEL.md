# PigLedger 1.4.0：固定雲端網址與保留資料的更新

正式網站：[555-rho-nine.vercel.app](https://555-rho-nine.vercel.app/)，沿用 Vercel pig13／555、GitHub aa0985854612-pixel/555 的 main、既有 Turso。原farmadmin保留，沒有清空資料或重新建庫。手機Safari／Chrome開網址、登入、加入主畫面；筆電不用保持開機。

## 一般程式更新

推送 GitHub main 會由既有Vercel Git整合自動部署。根目錄`./`、Framework Other、Python3.12、原`vercel.json`，沒有前端建置命令或輸出目錄。保留Production伺服器環境變數：

| 名稱 | 內容 |
| --- | --- |
| TURSO_DATABASE_URL | 既有資料庫libsql／HTTPS網址 |
| TURSO_AUTH_TOKEN | 同一資料庫可讀寫金鑰，敏感值 |

修改環境變數需要重新部署。不要填NEXT_PUBLIC、不把資料庫金鑰放進前端／GitHub。VERCEL_TOKEN是維護用途，不是App密碼，日常伺服器不需要。Git部署不會自動上傳本地農場資料、Excel或變更正式資料庫結構。

## schema3→4更新（本次已執行，勿重新搬舊資料）

先備份正式資料，使用受保護執行環境的原資料庫金鑰：

```sh
python3 scripts/upgrade_cloud.py --prepare --ensure-role-accounts
# 新版部署Ready後完成版本標記
python3 scripts/upgrade_cloud.py
```

工具先建立持久雲端備份，交易內新增account_security，核對原records／users／requests／audit不變。準備階段保留schema3標記讓新舊部署交接，完成後標記4。一般API不執行schema修改；新版相容準備階段，舊版1.3.1不能直接回滾到標記4資料庫。回滾需使用相容schema4的修正版，或經明確維護安排還原完整備份，不能覆蓋後續正式登記。

`--ensure-role-accounts`只建立缺少的farmviewer／farmeditor／farmmanager，使用不同的隨機未知臨時密碼並要求設定，不重設同名帳號或原farmadmin。原管理員於「設定」產生一次性密碼設定連結，私下交給各人。密碼只存雜湊，管理員不能查看原密碼。

本次更新前已建立雲端備份，另以公開憑證加密取回離線備份，私鑰留在受保護維護環境；更新後再次備份。原55筆紀錄、原帳號保留，新增一份新版Excel來源，補登一筆有來源的入場均重；沒有新增重複棟舍、批次或日常異動。原管理員雜湊逐欄核對未變。詳細農場數字與私密備份不放入公開程式包。

新版Excel先以現況產生預覽與修訂指紋，再交易內核對並套用無爭議來源。已手動登記的事件不重複入帳；衝突批次保留App，來源原文仍可下載。再次匯入相同來源略過。不要把本地過時SQLite再次移入正式庫。

## 備份與搬家

管理員在「設定」下載完整JSON備份並私下保管；唯讀不能下載包含帳號的備份。內部備份與正式資料同庫，請另行保存離線副本。普通程式包不含任何農場資料。`scripts/migrate_cloud.py --db /private/existing.sqlite3`僅供搬到另一個空白資料庫；已使用的正式庫不是每次部署都重跑搬移。

## 驗證及交付

真實雲端已完成更新、原資料比對、原帳號後端登入／登出、來源重複匯入、歷史／CSV與來源均重讀取。Vercel Ready不等於所有手機情境通過。本環境對正式網域的直接連線遭代理CONNECT403；公開HTTPS瀏覽器、實體手機及跨裝置仍待現場驗收。詳見[1.4.0測試報告](TEST_REPORT_1.4.0.md)。

日常使用正式網址。完整程式與Docker／Vercel部署檔使用**release/pigledger-1.4.0.zip**及同名sha256。原始碼在GitHub main，舊版包保留不同檔名。
