(function () {
  const makeSortable = (table) => {
    const tbody = table.tBodies[0];
    const headers = Array.from(table.querySelectorAll("th[data-sort]"));

    const arrows = new Map();
    headers.forEach((th) => {
      const arrow = document.createElement("span");
      arrow.className = "arr";
      arrow.setAttribute("aria-hidden", "true");
      th.appendChild(arrow);
      arrows.set(th, arrow);
    });

    const glyph = (descending) => (descending ? "▼" : "▲");

    const markActive = (activeTh, descending) => {
      headers.forEach((th) => {
        arrows.get(th).textContent = th === activeTh ? glyph(descending) : "";
      });
    };

    headers.forEach((th) => {
      const colIndex = Array.from(th.parentNode.children).indexOf(th);
      const sortType = th.dataset.sort;
      let descending = th.dataset.first ? th.dataset.first === "desc" : sortType === "number";

      const initial = th.dataset.sorted;
      if (initial) {
        const isDescending = initial === "desc";
        markActive(th, isDescending);
        descending = !isDescending;
      }

      th.addEventListener("click", () => {
        // A rounds-row belongs to the row above it, so the pair moves as one.
        const groups = [];
        Array.from(tbody.rows).forEach((row) => {
          if (row.classList.contains("rounds-row") && groups.length) {
            groups[groups.length - 1].push(row);
          } else {
            groups.push([row]);
          }
        });
        groups.sort(([a], [b]) => {
          const av = a.cells[colIndex].textContent.trim();
          const bv = b.cells[colIndex].textContent.trim();
          if (sortType === "number") {
            return descending ? Number(bv) - Number(av) : Number(av) - Number(bv);
          }
          return descending ? bv.localeCompare(av) : av.localeCompare(bv);
        });
        groups.flat().forEach((row) => tbody.appendChild(row));
        markActive(th, descending);
        descending = !descending;
      });
    });
  };

  document.querySelectorAll("table[data-sortable]").forEach(makeSortable);

  const league = document.getElementById("league");
  if (!league) return;
  const tbody = league.tBodies[0];
  const chips = Array.from(document.querySelectorAll(".chip[data-player]"));
  const meta = document.getElementById("resultsMeta");
  const applyFilter = () => {
    const active = new Set(
      chips.filter((c) => c.classList.contains("active")).map((c) => c.dataset.player)
    );
    let shown = 0;
    Array.from(tbody.rows).forEach((row) => {
      const match = active.has(row.dataset.player);
      row.classList.toggle("hidden", !match);
      if (match) shown += 1;
    });
    if (meta) meta.textContent = shown + " entries";
  };
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      chip.classList.toggle("active");
      applyFilter();
    });
  });
})();
