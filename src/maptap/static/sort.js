(function () {
  const table = document.getElementById("league");
  if (!table) return;
  const tbody = table.tBodies[0];
  const headers = Array.from(table.querySelectorAll("th[data-sort]"));

  const arrows = new Map();
  headers.forEach((th) => {
    const arrow = document.createElement("span");
    arrow.className = "sort-arrow";
    arrow.setAttribute("aria-hidden", "true");
    th.appendChild(arrow);
    arrows.set(th, arrow);
  });

  const glyph = (descending) => (descending ? " ▼" : " ▲");

  const markActive = (activeTh, descending) => {
    headers.forEach((th) => {
      arrows.get(th).textContent = th === activeTh ? glyph(descending) : "";
    });
  };

  headers.forEach((th) => {
    const colIndex = Array.from(th.parentNode.children).indexOf(th);
    const sortType = th.dataset.sort;
    let descending = sortType === "number";

    const initial = th.dataset.sorted;
    if (initial) {
      const isDescending = initial === "desc";
      markActive(th, isDescending);
      descending = !isDescending;
    }

    th.addEventListener("click", () => {
      const rows = Array.from(tbody.rows);
      rows.sort((a, b) => {
        const av = a.cells[colIndex].textContent;
        const bv = b.cells[colIndex].textContent;
        if (sortType === "number") {
          return descending ? Number(bv) - Number(av) : Number(av) - Number(bv);
        }
        return descending ? bv.localeCompare(av) : av.localeCompare(bv);
      });
      rows.forEach((row) => tbody.appendChild(row));
      markActive(th, descending);
      descending = !descending;
    });
  });
})();
