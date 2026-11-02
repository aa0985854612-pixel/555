"use strict";
/* An index of existing ended batches. Records stay in their original ledgers. */
(() => {
  Object.assign(words, {
    endedRecords: ["已結束紀錄", "Lứa đã kết thúc"],
    endedHint: [
      "已結束的批次集中在這裡；可查詢原始明細、列印肉豬紀錄表，管理員也可更改狀態。",
      "Các lứa đã kết thúc ở đây. Xem bản ghi gốc, in bảng; quản trị có thể đổi trạng thái.",
    ],
    endedSearch: ["搜尋批號／棟舍", "Tìm mã lứa / chuồng"],
    endedEmpty: ["目前沒有已結束的紀錄。", "Chưa có lứa đã kết thúc."],
    endedNoMatch: [
      "沒有符合的已結束紀錄，請修改搜尋文字。",
      "Không tìm thấy lứa đã kết thúc; hãy đổi từ tìm kiếm.",
    ],
    clearedRecords: ["已清空紀錄", "Lứa đã xuất hết"],
    clearedHint: [
      "已清空但尚未標記結束的批次保留在這裡；已結束的資料請到「歷史紀錄 → 已結束紀錄」。",
      "Lứa xuất hết nhưng chưa kết thúc ở đây. Lứa đã kết thúc xem tại Lịch sử → Lứa đã kết thúc.",
    ],
  });
  const base = {
    build,
    translate,
    selections,
    enter,
    renderCurrent,
    clickAction,
  };
  let fingerprint = "",
    owner = null;
  const keyOf = (b) => b._cohort_key || b.name + "|" + b.entry_date;
  function renderArchive() {
    const root = $("#ended-records");
    if (!root || !data || !me) return;
    const ended = data.batches
      .filter((b) => b.status === "ended")
      .sort(
        (a, b) =>
          b.entry_date.localeCompare(a.entry_date) ||
          a.name.localeCompare(b.name, lang === "vi" ? "vi" : "zh-Hant", {
            numeric: true,
          }),
      );
    root.querySelector("summary").textContent =
      t("endedRecords") + " · " + ended.length;
    $("#open-ended-records").textContent =
      t("endedRecords") + " · " + ended.length;
    const search = $("#ended-search").value.trim().toLocaleLowerCase(),
      stamp = JSON.stringify([lang, me.id, me.role, search, ended, data.barns]);
    if (stamp === fingerprint) return;
    fingerprint = stamp;
    const groups = new Map();
    for (const b of ended) {
      const key = keyOf(b);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(b);
    }
    const visible = Array.from(groups.values())
      .map((members) =>
        members.filter(
          (b) =>
            !search ||
            [
              b.name,
              b.entry_date,
              data.barns.find((x) => x.id === b.barn_id)?.name,
            ]
              .join(" ")
              .toLocaleLowerCase()
              .includes(search),
        ),
      )
      .filter((members) => members.length);
    $("#ended-results").innerHTML =
      visible
        .map(
          (members) =>
            `<section class="ended-group"><h3>${esc(members[0].name)}</h3>${members.map((b) => `<article class="ended-record" data-ended-batch="${esc(b.id)}"><div><strong>${esc(data.barns.find((x) => x.id === b.barn_id)?.name || t("unassigned"))}</strong><span class="pill">${t("ended")}</span><small>${t("entryDate")} ${esc(b.entry_date)}</small></div><div class="actions"><button type="button" data-cleared-history="${esc(b.id)}">${t("viewHistory")}</button><button type="button" data-cleared-report="${esc(b.id)}">${t("weeklyReport")}</button>${me.role === "admin" ? `<button type="button" data-manage-batch="${esc(b.id)}">${t("manageBatchShort")}</button>` : ""}</div></article>`).join("")}</section>`,
        )
        .join("") ||
      `<p class="empty">${t(ended.length ? "endedNoMatch" : "endedEmpty")}</p>`;
  }
  function showArchive() {
    if (!me || !data) return;
    setPage("history", false);
    location.hash = "history";
    renderArchive();
    const root = $("#ended-records");
    root.open = true;
    renderCurrent();
    requestAnimationFrame(() => {
      root.scrollIntoView({ block: "start" });
      root.querySelector("summary").focus({ preventScroll: true });
    });
  }
  function clear() {
    fingerprint = "";
    $("#ended-results")?.replaceChildren();
    const input = $("#ended-search");
    if (input) input.value = "";
    if ($("#ended-records")) $("#ended-records").open = false;
  }
  build = () => {
    base.build();
    $("#page-history").insertAdjacentHTML(
      "afterbegin",
      `<details id="ended-records" class="card"><summary>${t("endedRecords")}</summary><p class="hint" data-i="endedHint">${t("endedHint")}</p><label><span data-i="endedSearch">${t("endedSearch")}</span><input id="ended-search" type="search" autocomplete="off"></label><div id="ended-results"></div></details>`,
    );
    $("#page-settings").insertAdjacentHTML(
      "afterbegin",
      `<div class="ended-settings-link"><button type="button" id="open-ended-records">${t("endedRecords")}</button></div>`,
    );
    $("#open-ended-records").onclick = showArchive;
    $("#ended-search").oninput = renderArchive;
  };
  clickAction = (event) => {
    if (event.target.closest("[data-cleared-history],[data-death-query]")) {
      $("#ended-records").open = false;
      document.dispatchEvent(new CustomEvent("pigledger:history-query-reset"));
    }
    return base.clickAction(event);
  };
  selections = (...args) => {
    const result = base.selections(...args);
    renderArchive();
    return result;
  };
  translate = (...args) => {
    const result = base.translate(...args);
    renderArchive();
    return result;
  };
  renderCurrent = async (...args) => {
    const result = await base.renderCurrent(...args);
    renderArchive();
    return result;
  };
  enter = async (user) => {
    if (owner !== user.id) {
      clear();
      owner = user.id;
    }
    const result = await base.enter(user);
    renderArchive();
    return result;
  };
  document.addEventListener("pigledger:ended-open", showArchive);
  document.addEventListener("pigledger:logout", () => {
    clear();
    owner = null;
  });
})();
