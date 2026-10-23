# 出豬存欄預覽：接續工作

需求：出豬登記選好棟舍、批號、日期與頭數後，即時顯示「目前存欄 → 本次出豬 → 出完剩餘」，例如159 → 80 → 79。僅明確按儲存才寫入資料。

已完成且已推送：GitHub aa0985854612-pixel/555 分支 codex/outgoing-stock-preview，功能提交26916f3517341e26ca2f3901805cc09cd4aab15c。556項單元/整合測試、9項出豬預覽瀏覽器情境、5項原有異動更正瀏覽器情境通過。手機預覽圖為本套件的outgoing-preview-mobile.png，資料均為合成範例。

尚未發布。可取到的GitHub主分支為2.0.35、470f940673343d064b581624717625d83b494d62。最後已知正式部署為2.0.43、dpl_5ePixDwMkYZh6ampYwRzHazE4ekK，來源提交3a6f81a93489ff6ab7d0d3e75d7da6cef2dc9a91。不要將2.0.35完整工作樹部署至正式站；須先透過授權的Vercel API取回目前正式版來源，再整合本功能，保留通知、體重估算等後續功能。正式站為https://555-rho-nine.vercel.app/，專案ID prj_fB27Wqr05EA0N49BRXALcqq1jO72，部署回傳ownerId team_fP6tZY7O15k9gaflqMRr7vCB。先解析正式alias確認目前部署，不要假設至今無新發布。

使用者已在Vercel建立新Token，並回報已更新Codex的VERCEL_TOKEN。本舊對話的API請求仍回403，GET /v5/user/tokens/current回Token not found；不得打印或索取聊天中的Token內容。環境草稿更新被平台拒絕，錯誤draft_not_editable（可能已發布或發布中）；嘗試新增VERCEL_RELEASE_TOKEN的宣告沒有成功，所以不能假設此欄位存在。需使用新工作環境核對既有VERCEL_TOKEN是否生效。不要要求使用者重複建立Token作為第一步。

恢復授權後：取回正式來源，以最新正式版本為基礎套用本套件outgoing-preview.patch（衝突時手動整合index.html與sw.js，保留正式版其他資產及裝置通知狀態）。腳本需在feed-bulk.js啟動前載入。新增CSS與JS並加入Service Worker資產列表，遞增正式版本及快取版本。以目前程式重新執行原有及本功能測試，再發布到原正式網址，確認伺服器Cron仍為每日UTC 02:00（台灣10:00），不重設VAPID金鑰或手機訂閱。

不要讀出Vercel敏感環境值、覆寫或初始化正式資料庫，也不要把舊資料備份匯入正式站。這個功能僅為顯示層改動；本次工作未存取正式農場資料，也未嘗試正式部署。
