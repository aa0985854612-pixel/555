# PigLedger 1.3.0：固定雲端網址

部署完成後，用手機 Safari／Chrome 開啟 Vercel 正式 HTTPS 網址、登入，再選「加入主畫面」。筆電可以關機，六個頁面共用雲端資料。

**2026-10-15 使用者已部署 [555-rho-nine.vercel.app](https://555-rho-nine.vercel.app/)，登入畫面顯示雲端資料庫尚未連接。** 此狀態依使用者截圖，維護環境未完成公網驗證，仍缺 Vercel 授權與 Turso 連線，HTTPS 請求收到環境代理403。GitHub 程式碼網址、localhost、原資料來源 `666-rust.vercel.app` 都不是這個 App 的正式使用入口。新網站需連接資料庫並私密移入資料後才可正式使用。

## 用原 Vercel 帳號建立專案

1. 登入原帳號，開啟 [匯入 555](https://vercel.com/new/import?s=https%3A%2F%2Fgithub.com%2Faa0985854612-pixel%2F555)。清單沒有 repository 時，授權 Vercel 的 GitHub App 存取 `aa0985854612-pixel/555`。
2. 專案名稱可用 `pigledger`；Framework Preset 選 **Other**，Root Directory 使用 repository 根目錄。Build Command、Output Directory 不指定其他 framework 的設定。根目錄已有 `vercel.json` 與 Python 3.12 設定。建立 App 專案即可，無須刪除原 `666` 網站。
3. 先至 [Turso 官網](https://turso.tech/) 進入登入／管理介面，使用 GitHub 登入，建立名為 `pigledger` 的資料庫。若已建立相同用途的資料庫，直接沿用。先前提供的 `vercel.com/marketplace/turso` 在使用者介面顯示404，不依賴此入口。Vercel 的 **Connect Database** 搜尋的是團隊已建立的資料庫，不是供應商搜尋；不用在那裡搜尋 Turso。建立後將平台提供的資料庫網址與存取金鑰填入 **555專案 → Environment Variables → Production**：

   | 名稱 | 內容 |
   | --- | --- |
   | `TURSO_DATABASE_URL` | 平台提供的 `libsql://…turso.io` 或 HTTPS 資料庫網址 |
   | `TURSO_AUTH_TOKEN` | 該資料庫的存取 token，設為敏感值 |

   若整合服務已提供同名項目，直接沿用。不要把 token 放入 GitHub、聊天、網址或 `NEXT_PUBLIC_` 欄位。預覽測試使用獨立測試資料庫。
4. 在維護環境安全設定提供相同資料庫連線，由維護人員完成下節的資料移入。**不用重新建立 farmadmin，也不用再填 Excel 與分棟數。** 實際資料已在維護環境核對並備份。
5. 按 Deploy／Redeploy，以 Vercel 專案頁顯示的 Production Domain 為準。`/api/health` 應回 `ok: true`、`version: 1.3.0`；未設定／未初始化資料庫時回 503，尚不能使用。

若由維護代理代為部署，另在維護環境的安全設定提供 `VERCEL_TOKEN`，不貼在聊天。這不是 App 密碼，也不需要放在 App 的 Vercel 環境變數。安全設定及必要網路變更套用後，代理可完成私密資料移入、部署與正式網址驗證。

本次新增網路與金鑰需求的環境設定被自動審核（ASB）拒絕，回覆僅為需檢查 requirements 和 allowed_domains，未提供細節；這些需求並未保存或套用。另已成功保存1.3.0的開發啟動說明。必要連線包括 `api.vercel.com`、實際Production網域及實際Turso資料庫主機；請在安全設定中設定並套用，無須公開金鑰。

## 私密原資料移入（維護人員執行）

實際 SQLite 在維護環境 `.data/pigledger.sqlite3`。帳號、工作簿與备份位於 Git 忽略的私密目錄，程式包不攜帶私人資料。移入前暫停正式登記，核對完成後改用新網址登記。

安全注入 `TURSO_DATABASE_URL`、`TURSO_AUTH_TOKEN`，在 repository 根目錄執行：

```sh
python3 scripts/migrate_cloud.py --db .data/pigledger.sqlite3
```

工具先用 SQLite Backup API 備份來源，再以單一遠端交易移入。保留 schema3、所有原始紀錄與 tombstone、帳號 ID／雜湊／角色／修訂、原始 Excel、audit seq、requests 去重資料；不搬移 sessions，新網址重新登入。核對完整內容 SHA-256 一致才提交；遠端已有不同資料時拒絕整批，不清庫、不覆蓋；完全一致則安全略過。

管理員仍可下載完整 JSON 備份、合併匯入。雲端內部更正前備份保存於受保護的持久資料庫，不寫進 Vercel 暫存檔案系統。它與正式資料在同一資料庫，不能取代另外保存的 JSON／平台災難復原備份，請定期下載私密備份。

## 正式網址驗證

- HTTPS、登入既有管理員、唯讀帳號拒絕寫入、Secure／HttpOnly Cookie。
- 24 棟、24 分棟批次、1 原始工作簿；截至 2026-10-14 剩餘 7,817 頭、合計出豬 1,361、死亡 193，育成率 97.94%。10/12 的20棟輸入為388；核對分配後10/14為383，分配仍標示暫定。
- 另一裝置看到相同資料，重複儲存只計一次，更正版本衝突拒絕覆蓋。
- Redeploy 後資料與帳號保留。
- Android、iPhone、iPad 實機、行動網路與加入主畫面。

正式公網、真实 Turso、實機及 Redeploy 驗證目前尚未執行。Vercel HTTP 大小限制通常為4.5 MB，大型工作簿或備份由維護人員使用移入工具。費用及額度依 Vercel／Turso 實際方案，不承諾永久免費。沒有自動叫料、配送或採食預測工作。

## 更新與交付檔案

以 GitHub `main` 部署，更新程式仍沿用相同 `TURSO_DATABASE_URL` 與帳號。版本及 PWA 快取為1.3.0，API 不進離線快取，未成功送出的紀錄顯示尚未確認。遠端交易保留連線 baton，條件式 batch 確保失敗時不提交部分寫入；伺服器驗證權限、revision 與去重鍵。登入嘗試限制也存於共用資料庫。

部署使用 **GitHub repository 根目錄**（`vercel.json`、`pyproject.toml`、`api/`、`app/`）；離線交付用 **pigledger-1.3.0.zip**。手機直接開正式網站，不下載 ZIP、不執行 bat、不用檔案預覽。
