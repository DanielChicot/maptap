(function () {
  const table = document.getElementById("league");
  if (!table) return;
  const tbody = table.tBodies[0];
  const headers = table.querySelectorAll("th[data-sort]");

  headers.forEach((th) => {
    const colIndex = Array.from(th.parentNode.children).indexOf(th);
    const sortType = th.dataset.sort;
    let descending = true;
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
      descending = !descending;
      rows.forEach((row) => tbody.appendChild(row));
    });
  });
})();
