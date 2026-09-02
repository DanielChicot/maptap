(function () {
  const toggle = (row) => {
    const details = row.nextElementSibling;
    if (!details || !details.classList.contains("rounds-row")) return;
    const opening = details.hidden;
    details.hidden = !opening;
    row.setAttribute("aria-expanded", String(opening));
  };

  document.querySelectorAll("tr[aria-expanded]").forEach((row) => {
    row.addEventListener("click", () => toggle(row));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggle(row);
      }
    });
  });
})();
