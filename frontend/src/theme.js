// Qorong'i / och tema: tanlov localStorage'da, standart — qurilma sozlamasi.
export function getTheme() {
  try {
    const saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch { /* ruxsat yo'q */ }
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("theme", theme); } catch { /* ignore */ }
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "light" ? "#f5f3ee" : "#0f1115");
}
