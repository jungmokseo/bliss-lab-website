/* Progressive enhancement only. All research content lives in static HTML. */
(() => {
  "use strict";

  const start = () => {
    const korean = document.documentElement.lang.toLowerCase().startsWith("ko");

    // The navigation is visible without JavaScript. Only a complete menu setup
    // enables the CSS that collapses it on mobile.
    document.querySelectorAll(".site-header").forEach((header, index) => {
      const toggle = header.querySelector(".menu-toggle");
      const nav = header.querySelector(".nav");
      if (!toggle || !nav) return;
      if (!nav.id) nav.id = `site-nav-${index + 1}`;
      toggle.setAttribute("aria-controls", nav.id);
      if (toggle.tagName === "BUTTON") toggle.setAttribute("type", "button");
      const mobile = window.matchMedia("(max-width: 800px)");
      const openLabel = toggle.dataset.openLabel || (korean ? "메뉴 열기" : "Open menu");
      const closeLabel = toggle.dataset.closeLabel || (korean ? "메뉴 닫기" : "Close menu");
      const update = (open) => {
        header.dataset.menuOpen = String(open);
        toggle.setAttribute("aria-expanded", String(open));
        toggle.setAttribute("aria-label", open ? closeLabel : openLabel);
        const label = toggle.querySelector(".menu-label");
        if (label) label.textContent = open ? (korean ? "닫기" : "Close") : (korean ? "메뉴" : "Menu");
      };
      update(!mobile.matches);
      header.dataset.menuReady = "true";
      toggle.addEventListener("click", () => update(header.dataset.menuOpen !== "true"));
      nav.addEventListener("click", (event) => {
        if (mobile.matches && event.target.closest("a")) update(false);
      });
      header.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && mobile.matches && header.dataset.menuOpen === "true") {
          update(false);
          toggle.focus();
        }
      });
      const resized = () => update(!mobile.matches);
      if (typeof mobile.addEventListener === "function") mobile.addEventListener("change", resized);
      else mobile.addListener(resized);
    });

    const search = document.querySelector("#search");
    const theme = document.querySelector("#theme-filter");
    const level = document.querySelector("#level-filter");
    const items = Array.from(document.querySelectorAll("[data-filter-item]"));
    if ((!search && !theme && !level) || items.length === 0) return;
    const result = document.querySelector("#result-count");
    const empty = document.querySelector(".empty-state");
    const controls = [search, theme, level].filter(Boolean);
    const normalize = (text) => String(text || "").normalize("NFKC").toLocaleLowerCase().replace(/\s+/g, " ").trim();
    const tokens = (text) => normalize(text).split(/[\s,;|]+/).filter(Boolean);
    const records = items.map((element) => ({
      element,
      search: normalize(`${element.dataset.search || ""} ${element.textContent}`),
      themes: tokens(element.dataset.theme),
      levels: tokens(element.dataset.level),
    }));
    const selected = (control) => {
      const value = normalize(control ? control.value : "");
      return value === "all" ? "" : value;
    };
    const apply = () => {
      const words = normalize(search ? search.value : "").split(" ").filter(Boolean);
      const themeValue = selected(theme);
      const levelValue = selected(level);
      let visible = 0;
      records.forEach((record) => {
        const matches = words.every((word) => record.search.includes(word))
          && (!themeValue || record.themes.includes(themeValue))
          && (!levelValue || record.levels.includes(levelValue));
        record.element.hidden = !matches;
        if (matches) visible += 1;
      });
      if (result) result.textContent = korean
        ? `전체 ${records.length}편 중 ${visible}편 표시`
        : `Showing ${visible} of ${records.length} papers`;
      if (empty) empty.hidden = visible !== 0;
    };
    if (result) {
      result.setAttribute("role", "status");
      result.setAttribute("aria-live", "polite");
      result.setAttribute("aria-atomic", "true");
    }
    controls.forEach((control) => {
      control.disabled = false;
      control.addEventListener(control === search ? "input" : "change", apply);
      const filters = control.closest(".filters");
      if (filters) filters.dataset.filtersReady = "true";
    });
    document.querySelectorAll("[data-reset-filters]").forEach((button) => {
      button.addEventListener("click", () => {
        if (search) search.value = "";
        [theme, level].filter(Boolean).forEach((control) => {
          const allOption = Array.from(control.options).find((option) => !option.value || option.value === "all");
          if (allOption) control.value = allOption.value;
          else control.selectedIndex = 0;
        });
        apply();
        if (search) search.focus();
      });
    });
    const form = controls[0].closest("form");
    if (form) {
      form.addEventListener("submit", (event) => event.preventDefault());
      form.addEventListener("reset", () => window.setTimeout(apply, 0));
    }
    apply();
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
