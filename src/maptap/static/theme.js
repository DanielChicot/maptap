(function () {
  const root = document.documentElement;
  const stored = localStorage.getItem("maptap-theme") || "dark";
  root.setAttribute("data-theme", stored);

  const btn = document.getElementById("themeBtn");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("maptap-theme", next);
  });
})();
