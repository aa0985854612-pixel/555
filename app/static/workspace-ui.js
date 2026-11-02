"use strict";
/* Shared, progressive workspace components. Original record handlers stay in charge. */
(() => {
  Object.assign(words, {
    uiEstimateLink: ["查看體重估算", "Xem cân nặng ước tính"],
    uiPeriodDistribution: ["各批次死亡分布", "Phân bố heo chết theo lứa"],
    uiRecordLead: [
      "選擇棟舍與批次，填入本次異動頭數。",
      "Chọn chuồng và lứa, nhập số con thay đổi lần này.",
    ],
    uiFeedLead: [
      "同一天可逐筆加入清單，核對後一起儲存。",
      "Thêm từng mục cùng ngày, đối chiếu rồi lưu cùng lúc.",
    ],
    uiWeightLead: [
      "選好棟舍後，依欄位填入每頭重量。",
      "Chọn chuồng rồi nhập cân nặng từng con theo ô.",
    ],
    uiSettingsLead: [
      "棟舍、批次與進場資料集中管理；原始紀錄與修改歷程持續保留。",
      "Quản lý chuồng, lứa và dữ liệu nhập; giữ bản gốc cùng lịch sử sửa đổi.",
    ],
    uiSearchList: ["搜尋目前清單", "Tìm trong danh sách"],
    uiRows: ["每頁", "Mỗi trang"],
    uiAllRows: ["全部", "Tất cả"],
    uiPrevious: ["上一頁", "Trước"],
    uiNext: ["下一頁", "Sau"],
    uiRowsShown: ["{from}–{to}／{total} 筆", "{from}–{to} / {total} mục"],
    uiNoMatches: [
      "沒有符合的資料，可修改搜尋文字。",
      "Không tìm thấy; thử đổi từ tìm kiếm.",
    ],
    uiSearchScope: [
      "搜尋與排序僅影響這份清單；匯出依上方查詢條件。",
      "Tìm và sắp xếp chỉ trong danh sách này; xuất theo bộ lọc phía trên.",
    ],
    uiRequired: ["請填寫這個欄位。", "Vui lòng điền trường này."],
    uiInvalid: ["請檢查這個欄位的內容。", "Kiểm tra nội dung trường này."],
    uiSort: ["排序", "Sắp xếp"],
    uiDirection: ["反轉排序", "Đảo thứ tự"],
    uiSkip: ["跳至主要內容", "Đến nội dung chính"],
    uiNav: ["主要功能", "Chức năng chính"],
  });
  const paths = {
    daily:
      "M12 3v4m0 10v4M3 12h4m10 0h4M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10Zm0 2v3l2 1",
    stats: "M4 19h16M6 15v-4m6 4V5m6 10V8",
    history: "M3 11a9 9 0 1 1 3 8M3 4v7h7m2-5v6l4 2",
    feed: "M4 8h16l-1 12H5L4 8Zm2 0V4h12v4m-8 5h4",
    weights: "M12 4v16M5 20h14M4 7h16M6 7 3 14h6L6 7Zm12 0-3 7h6l-3-7Z",
    settings:
      "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm-1-5h2l1 3 3 1 3-1 1 2-2 2v4l2 2-1 2-3-1-3 1-1 3h-2l-1-3-3-1-3 1-1-2 2-2v-4L3 8l1-2 3 1 3-1 1-3Z",
    logout: "M10 5H5v14h5m4-12 5 5-5 5m-5-5h10",
  };
  const svg = (path) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${path}"/></svg>`;
  const base = {
    build,
    translate,
    renderCurrent,
    selections,
    enter,
    api,
    persistPending,
    statHTML,
  };
  let observer = null,
    queued = false,
    owner = null,
    writes = 0,
    tableSequence = 0,
    fieldSequence = 0,
    focusedSearch = null;
  const tableMemory = new Map(),
    tableInstances = new WeakMap(),
    activeTables = new Set();
  function label(key, values = {}) {
    return Object.entries(values).reduce(
      (s, [k, v]) => s.replace("{" + k + "}", v),
      t(key),
    );
  }
  function visiblePage() {
    return document.querySelector(".page:not([hidden])");
  }
  function surface(formId, lead) {
    const form = $("#" + formId);
    if (!form) return;
    const box = form.closest(".card");
    if (!box) return;
    box.classList.add("ui-surface", "ui-form-section");
    if (lead && !box.querySelector(":scope > p")) {
      const text = document.createElement("p");
      text.className = "ui-section-lead";
      text.dataset.i = lead;
      text.textContent = t(lead);
      box.querySelector("h2")?.after(text);
    }
  }
  function formHeading(id) {
    const form = $("#" + id);
    if (!form || form.querySelector(".ui-form-heading")) return;
    const box = form.closest(".card"),
      heading = box?.querySelector(":scope>h2"),
      date = form.elements.namedItem("date");
    if (!heading || !date) return;
    const row = document.createElement("div");
    row.className = "ui-form-heading";
    const label = date.closest("label");
    label.classList.add("ui-form-date");
    row.append(heading, label);
    form.prepend(row);
    const leads = Array.from(box.children).filter(
      (child) => child.tagName === "P",
    );
    let anchor = row;
    for (const lead of leads) {
      lead.classList.add("ui-section-lead");
      anchor.after(lead);
      anchor = lead;
    }
  }
  function labels() {
    const repair = $(".home-report-shortcut");
    if (repair) repair.hidden = !me || current !== "daily";
    $("#nav")?.setAttribute("aria-label", t("uiNav"));
    document.querySelectorAll("#nav a").forEach((a) => {
      if (a.classList.contains("active"))
        a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    const logout = $("#logout");
    if (logout) {
      logout.setAttribute("aria-label", t("logout"));
      logout.title = t("logout");
    }
    for (const item of Array.from(activeTables)) {
      if (!item.table.isConnected) {
        activeTables.delete(item);
        continue;
      }
      item.translate();
    }
  }
  function writeState() {
    document.body.classList.toggle("ui-writing", writes > 0);
    document
      .querySelectorAll("form")
      .forEach((f) =>
        f.setAttribute(
          "aria-busy",
          String(
            !!(writes && f.dataset.uiWriting === "1") ||
              (pending?.formId === f.id && !!retryPending.busy),
          ),
        ),
      );
  }
  function validation() {
    document.addEventListener(
      "invalid",
      (event) => {
        const control = event.target;
        if (
          !control.matches("input,select,textarea") ||
          control.closest("#weekly-print-root")
        )
          return;
        const holder = control.closest("label");
        if (!holder) return;
        if (!control.id) control.id = "ui-field-" + ++fieldSequence;
        const id = control.id + "-error";
        let note = document.getElementById(id);
        if (!note) {
          note = document.createElement("span");
          note.id = id;
          note.className = "ui-field-error";
          holder.append(note);
        }
        note.dataset.i = control.validity.valueMissing
          ? "uiRequired"
          : "uiInvalid";
        note.textContent = t(note.dataset.i);
        control.setAttribute("aria-invalid", "true");
        const described = new Set(
          (control.getAttribute("aria-describedby") || "")
            .split(" ")
            .filter(Boolean),
        );
        described.add(id);
        control.setAttribute("aria-describedby", [...described].join(" "));
      },
      true,
    );
    document.addEventListener("input", (event) => {
      const control = event.target;
      if (control.matches("input,select,textarea") && control.validity.valid) {
        control.removeAttribute("aria-invalid");
        const note = document.getElementById(control.id + "-error");
        if (note) {
          note.remove();
          const rest = (control.getAttribute("aria-describedby") || "")
            .split(" ")
            .filter((id) => id && id !== note.id);
          if (rest.length)
            control.setAttribute("aria-describedby", rest.join(" "));
          else control.removeAttribute("aria-describedby");
        }
      }
    });
  }
  function tableKey(table, host) {
    return (
      host.id +
      "|" +
      (host.id === "history-results"
        ? val($("#history-filter"), "record_kind")
        : "") +
      "|" +
      table.querySelectorAll("thead th").length
    );
  }
  function enhanceTables() {
    document
      .querySelectorAll(
        "#history-results .table-wrap>table,#weight-results .table-wrap>table,#usage-results .table-wrap>table,#delivery-results .table-wrap>table",
      )
      .forEach((table) => {
        if (
          tableInstances.has(table) ||
          !table.tBodies[0] ||
          table.closest("dialog")
        )
          return;
        const rows = Array.from(table.tBodies[0].rows);
        let renderedOrder = rows.slice();
        if (!rows.length) return;
        const host = table.closest(
            "#history-results,#weight-results,#usage-results,#delivery-results",
          ),
          key = tableKey(table, host),
          state = tableMemory.get(key) || {
            search: "",
            page: 0,
            size: 25,
            column: -1,
            reverse: false,
          };
        tableMemory.set(key, state);
        const tools = document.createElement("div");
        tools.className = "ui-table-tools";
        const identity = "ui-list-" + ++tableSequence;
        table.id = table.id || identity;
        tools.innerHTML = `<label><span data-i="uiSearchList">${esc(t("uiSearchList"))}</span><input type="search" autocomplete="off" aria-controls="${table.id}"></label><label><span data-i="uiRows">${esc(t("uiRows"))}</span><select aria-controls="${table.id}"><option value="25">25</option><option value="50">50</option><option value="0">${esc(t("uiAllRows"))}</option></select></label>`;
        tools.title = t("uiSearchScope");
        const search = tools.querySelector("input"),
          size = tools.querySelector("select");
        search.value = state.search;
        size.value = String(state.size);
        const footer = document.createElement("div");
        footer.className = "ui-table-footer";
        footer.innerHTML = `<output aria-live="polite"></output><div class="actions"><button type="button" data-ui-prev>${esc(t("uiPrevious"))}</button><button type="button" data-ui-next>${esc(t("uiNext"))}</button></div>`;
        const empty = document.createElement("div");
        empty.className = "ui-table-empty";
        empty.hidden = true;
        empty.setAttribute("role", "status");
        const wrapper = table.closest(".table-wrap");
        wrapper.classList.add("ui-mobile-records");
        table.setAttribute("role", "table");
        table.tBodies[0].setAttribute("role", "rowgroup");
        rows.forEach((row) => {
          row.setAttribute("role", "row");
          Array.from(row.cells).forEach((cell) =>
            cell.setAttribute("role", "cell"),
          );
        });
        wrapper.before(tools);
        wrapper.after(footer);
        wrapper.append(empty);
        const heads = Array.from(table.querySelectorAll("thead th")),
          sortable = heads.map((th, index) => {
            if (
              th.querySelector("input,select") ||
              (index === heads.length - 1 &&
                rows.some((row) => row.cells[index]?.querySelector("button")))
            )
              return null;
            const button = document.createElement("button");
            button.type = "button";
            button.className = "ui-sort";
            button.append(...th.childNodes);
            th.append(button);
            th.scope = "col";
            button.addEventListener("click", (event) => {
              event.preventDefault();
              event.stopPropagation();
              state.reverse = state.column === index ? !state.reverse : false;
              state.column = index;
              state.page = 0;
              render();
            });
            return button;
          });
        const order = document.createElement("div");
        order.className = "ui-table-order";
        order.innerHTML = `<label><span>${esc(t("uiSort"))}</span><select></select></label><button type="button" title="${esc(t("uiDirection"))}">↕</button>`;
        tools.append(order);
        const orderSelect = order.querySelector("select");
        orderSelect.onchange = () => {
          state.column = Number(orderSelect.value);
          state.reverse = false;
          state.page = 0;
          render();
        };
        order.querySelector("button").onclick = (event) => {
          event.preventDefault();
          event.stopPropagation();
          if (state.column < 0) state.column = 0;
          state.reverse = !state.reverse;
          state.page = 0;
          render();
        };
        const collate = new Intl.Collator(undefined, {
          numeric: true,
          sensitivity: "base",
        });
        function numeric(text) {
          const normalized =
            lang === "vi"
              ? text.replace(/\./g, "").replace(/,/g, ".")
              : text.replace(/,/g, "");
          const match = normalized
            .trim()
            .match(
              /^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(kg|公斤|噸|tấn|t|%|頭|隻|con)?$/iu,
            );
          return match
            ? Number(match[1]) *
                (/^(噸|tấn|t)$/iu.test(match[2] || "") ? 1000 : 1)
            : null;
        }
        function render() {
          const query = state.search.trim().toLocaleLowerCase();
          let filtered = rows.filter(
            (row) =>
              !query || row.textContent.toLocaleLowerCase().includes(query),
          );
          if (state.column >= 0) {
            const n = state.column;
            filtered.sort((a, b) => {
              const av = a.cells[n]?.textContent.trim() || "",
                bv = b.cells[n]?.textContent.trim() || "";
              const an = numeric(av),
                bn = numeric(bv);
              return (
                (an !== null && bn !== null
                  ? an - bn
                  : collate.compare(av, bv)) * (state.reverse ? -1 : 1)
              );
            });
          }
          const per = state.size || Math.max(1, filtered.length),
            last = Math.max(0, Math.ceil(filtered.length / per) - 1);
          state.page = Math.min(state.page, last);
          if (
            renderedOrder.length !== filtered.length ||
            renderedOrder.some((row, i) => row !== filtered[i])
          ) {
            filtered.forEach((row) => table.tBodies[0].append(row));
            renderedOrder = filtered.slice();
          }
          rows.forEach((row) => (row.hidden = true));
          filtered.forEach((row, index) => {
            row.hidden =
              index < state.page * per || index >= (state.page + 1) * per;
          });
          const from = filtered.length ? state.page * per + 1 : 0,
            to = Math.min(filtered.length, (state.page + 1) * per);
          footer.querySelector("output").textContent = label("uiRowsShown", {
            from,
            to,
            total: filtered.length,
          });
          footer.querySelector("[data-ui-prev]").disabled = state.page === 0;
          footer.querySelector("[data-ui-next]").disabled = state.page >= last;
          empty.hidden = filtered.length > 0;
          empty.textContent = t("uiNoMatches");
          table.hidden = !filtered.length;
          orderSelect.value = String(state.column);
          heads.forEach((head, index) => {
            if (sortable[index])
              head.setAttribute(
                "aria-sort",
                state.column === index
                  ? state.reverse
                    ? "descending"
                    : "ascending"
                  : "none",
              );
          });
        }
        search.addEventListener("input", () => {
          state.search = search.value;
          state.page = 0;
          render();
        });
        search.addEventListener("focus", () => (focusedSearch = key));
        size.addEventListener("change", () => {
          state.size = Number(size.value);
          state.page = 0;
          render();
        });
        footer.querySelector("[data-ui-prev]").onclick = (event) => {
          event.preventDefault();
          event.stopPropagation();
          state.page--;
          render();
        };
        footer.querySelector("[data-ui-next]").onclick = (event) => {
          event.preventDefault();
          event.stopPropagation();
          state.page++;
          render();
        };
        const component = {
          table,
          translate() {
            order.querySelector("label>span").textContent = t("uiSort");
            order.querySelector("button").title = t("uiDirection");
            order
              .querySelector("button")
              .setAttribute("aria-label", t("uiDirection"));
            orderSelect.innerHTML =
              '<option value="-1">' +
              esc(t("all")) +
              "</option>" +
              heads
                .map((head, index) =>
                  sortable[index]
                    ? '<option value="' +
                      index +
                      '">' +
                      esc(head.textContent) +
                      "</option>"
                    : "",
                )
                .join("");
            rows.forEach((row) =>
              Array.from(row.cells).forEach((cell, index) => {
                cell.dataset.uiLabel = heads[index]?.textContent || "";
                cell.classList.toggle(
                  "ui-cell-actions",
                  !!cell.querySelector("button"),
                );
                cell.classList.toggle(
                  "ui-cell-wide",
                  index === heads.length - 1 ||
                    cell.textContent.trim().length > 45,
                );
              }),
            );
            tools.title = t("uiSearchScope");
            tools.querySelector("[data-i=uiSearchList]").textContent =
              t("uiSearchList");
            tools.querySelector("[data-i=uiRows]").textContent = t("uiRows");
            size.querySelector('[value="0"]').textContent = t("uiAllRows");
            footer.querySelector("[data-ui-prev]").textContent =
              t("uiPrevious");
            footer.querySelector("[data-ui-next]").textContent = t("uiNext");
            sortable.forEach((button) => {
              if (button)
                button.setAttribute(
                  "aria-label",
                  button.textContent + " · " + t("uiSort"),
                );
            });
            render();
          },
        };
        tableInstances.set(table, component);
        activeTables.add(component);
        component.translate();
        if (
          focusedSearch === key &&
          (!document.activeElement || document.activeElement === document.body)
        )
          search.focus({ preventScroll: true });
      });
  }
  function enhance() {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      ["movement-form", "feed-order-form", "weighing-form"].forEach(
        formHeading,
      );
      enhanceTables();
      document
        .querySelectorAll("dialog>.actions")
        .forEach((box) => box.classList.add("ui-dialog-actions"));
      labels();
    });
  }
  build = () => {
    base.build();
    document.body.classList.add("ui-workspace");
    document.body.insertAdjacentHTML(
      "afterbegin",
      `<button type="button" class="ui-skip" data-i="uiSkip">${esc(t("uiSkip"))}</button><div class="ui-loading-bar" aria-hidden="true"></div>`,
    );
    $(".ui-skip").onclick = () => {
      const target = me ? $("#page-title") : $("#login-form input");
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: "start" });
    };
    for (const link of document.querySelectorAll("#nav a")) {
      const icon = link.querySelector(".icon");
      if (icon && paths[link.dataset.page])
        icon.innerHTML = svg(paths[link.dataset.page]);
    }
    $("#nav").addEventListener("click", (event) => {
      if (event.target.closest("a[data-page]"))
        requestAnimationFrame(() => {
          $("#page-title").focus({ preventScroll: true });
          window.scrollTo(0, 0);
        });
    });
    const logout = $("#logout");
    delete logout.dataset.i;
    logout.innerHTML =
      svg(paths.logout) +
      `<span class="ui-logout-label" data-i="logout">${esc(t("logout"))}</span>`;
    surface("movement-form", "uiRecordLead");
    surface("feed-order-form");
    surface("weighing-form", "uiWeightLead");
    surface("login-form");
    surface("activation-form");
    document.querySelectorAll(".filters").forEach((form) => {
      const box = form.closest(".card");
      if (box && !box.closest("details")) box.classList.add("ui-query");
    });
    $("#feed-order-form")
      .elements.feed_bin_id.closest("label")
      .classList.add("ui-bin-field");
    const entry = $("#daily-entry"),
      review = $("#daily-review");
    if (entry && review) {
      const layout = document.createElement("div");
      layout.className = "ui-daily-layout";
      entry.before(layout);
      layout.append(entry, review);
    }
    const weighing = $("#weighing-form").closest(".card"),
      estimate = $("#growth-estimates");
    if (weighing && estimate) {
      const layout = document.createElement("div");
      layout.className = "ui-weights-layout";
      $("#page-weights").prepend(layout);
      layout.append(weighing, estimate);
      const jump = document.createElement("button");
      jump.type = "button";
      jump.className = "ui-estimate-link";
      jump.dataset.i = "uiEstimateLink";
      jump.textContent = t("uiEstimateLink");
      jump.onclick = () =>
        estimate.scrollIntoView({
          block: "start",
          behavior: matchMedia("(prefers-reduced-motion:reduce)").matches
            ? "auto"
            : "smooth",
        });
      $("#weighing-form").before(jump);
    }
    const shortcut = $("#page-daily .home-report-shortcut");
    if (shortcut) {
      $(".content .page-heading").before(shortcut);
      const pig = document.createElement("img");
      pig.src = "/repair-pig-v2.1.2.png";
      pig.alt = "";
      pig.width = pig.height = 64;
      pig.setAttribute("aria-hidden", "true");
      shortcut.querySelector("a").prepend(pig);
    }
    const settings = $("#page-settings");
    settings.insertAdjacentHTML(
      "afterbegin",
      `<div class="ui-settings-intro">${svg(paths.settings)}<p data-i="uiSettingsLead">${esc(t("uiSettingsLead"))}</p></div>`,
    );
    // Keep the public title and date in one shell; related details stay in their sections.
    $("#page-title").tabIndex = -1;
    $("#nav").setAttribute("aria-label", t("uiNav"));
    validation();
    document.addEventListener("focusin", (event) => {
      if (!event.target.closest(".ui-table-tools")) focusedSearch = null;
    });
    observer = new MutationObserver((records) => {
      if (
        records.some((record) =>
          Array.from(record.addedNodes).some(
            (node) =>
              node.nodeType === 1 &&
              (node.matches?.("table,.table-wrap") ||
                node.querySelector?.("table")),
          ),
        )
      )
        enhance();
    });
    observer.observe($("#pages"), { childList: true, subtree: true });
    enhance();
    labels();
  };
  translate = (...args) => {
    const result = base.translate(...args);
    labels();
    return result;
  };
  renderCurrent = async (...args) => {
    const result = await base.renderCurrent(...args);
    enhance();
    labels();
    return result;
  };
  selections = (...args) => {
    const result = base.selections(...args);
    labels();
    return result;
  };
  enter = async (user) => {
    if (owner !== user.id) {
      tableMemory.clear();
      focusedSearch = null;
      owner = user.id;
    }
    return base.enter(user);
  };
  statHTML = (s) => {
    const markup = base.statHTML(s),
      template = document.createElement("template");
    template.innerHTML = markup;
    const values = new Map(
      (s.death_groups || s.cohorts || []).map((group) => [
        group.cohort,
        group.period_deaths,
      ]),
    );
    const known = [...values.values()].filter(Number.isFinite),
      max = Math.max(0, ...known);
    template.content.querySelectorAll("[data-period-cohort]").forEach((row) => {
      const count = values.get(row.dataset.periodCohort);
      if (!Number.isFinite(count)) return;
      const bar = document.createElement("div");
      bar.className = "ui-period-bar";
      bar.setAttribute("aria-hidden", "true");
      const fill = document.createElement("span");
      fill.style.width = (max ? (count / max) * 100 : 0) + "%";
      bar.append(fill);
      row.querySelector(".period-row")?.after(bar);
    });
    const section = template.content.querySelector(".period-breakdown");
    if (section) {
      const heading = document.createElement("h2");
      heading.dataset.i = "uiPeriodDistribution";
      heading.textContent = t("uiPeriodDistribution");
      section.prepend(heading);
    }
    return template.innerHTML;
  };
  persistPending = (...args) => {
    const result = base.persistPending(...args);
    writeState();
    return result;
  };
  api = async (path, options = {}) => {
    const writing =
        options.method &&
        options.method !== "GET" &&
        !/preview(?:\?|$)/.test(path),
      form = document.activeElement?.closest("form");
    if (writing) {
      writes++;
      if (form) form.dataset.uiWriting = "1";
      writeState();
    }
    try {
      return await base.api(path, options);
    } finally {
      if (writing) {
        writes = Math.max(0, writes - 1);
        if (form) delete form.dataset.uiWriting;
        writeState();
      }
    }
  };
  document.addEventListener("pigledger:history-query-reset", () => {
    for (const [key, state] of tableMemory) {
      if (key.startsWith("history-results|")) {
        state.search = "";
        state.page = 0;
      }
    }
    const search = $("#history-results .ui-table-tools input[type=search]");
    if (search) {
      search.value = "";
      search.dispatchEvent(new Event("input"));
    }
    if (focusedSearch?.startsWith("history-results|")) focusedSearch = null;
  });
  document.addEventListener("pigledger:logout", () => {
    tableMemory.clear();
    focusedSearch = null;
    owner = null;
  });
})();
