(function () {
  const table = document.getElementById("league");
  if (!table) return;
  const tbody = table.tBodies[0];
  const headers = table.querySelectorAll("th[data-sort]");

  headers.forEach((th, headerIndex) => {
    const colIndex = Array.from(th.parentNode.children).indexOf(th);
    let descending = true;
    th.addEventListener("click", () => {
      const rows = Array.from(tbody.rows);
      rows.sort((a, b) => {
        const av = Number(a.cells[colIndex].textContent);
        const bv = Number(b.cells[colIndex].textContent);
        return descending ? bv - av : av - bv;
      });
      descending = !descending;
      rows.forEach((row) => tbody.appendChild(row));
    });
  });
})();
