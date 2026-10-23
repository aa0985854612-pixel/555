# 出豬預覽目前狀態

功能已整合至2.0.44，程式與發布驗證見docs/OUTGOING_PREVIEW.md、docs/TEST_REPORT_2.0.44.md。後續作業請先確認VERSION、GitHub main及正式網址實際版本，不要以舊交接壓縮檔整份覆寫。

正式網址：https://555-rho-nine.vercel.app/ 。發布基礎為從正式部署取回且核對全部內容雜湊的2.0.43程式；原本只存在舊工作環境的功能已恢復。完整程式包為release/pigledger-2.0.44.zip。先前outgoing-preview-handoff.zip僅為功能備份，不是完整正式版。

Vercel權限曾因舊Token與Codex環境草稿衝突受阻，後改用Vercel官方裝置授權。認證資料只放在私有工作環境，未加入Git或程式包。若日後權限失效，先檢查既有授權及環境狀態，不要要求使用者在聊天貼Token。

此功能不需要資料庫移轉。保留目前全部農場紀錄、帳號、工作簿及通知訂閱；不要匯入歷史資料庫備份來恢復程式碼。部署與讀取檢查只能使用既有正式資料，不能重設帳號或VAPID金鑰。
