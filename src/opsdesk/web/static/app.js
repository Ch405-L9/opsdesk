// Progressive enhancement only: click a table header to sort; "/" focuses search.
document.querySelectorAll("table[data-sortable] th").forEach((th, idx) => {
  th.addEventListener("click", () => {
    const tbody = th.closest("table").tBodies[0];
    const dir = th.dataset.dir === "asc" ? "desc" : "asc";
    th.dataset.dir = dir;
    const rows = Array.from(tbody.rows);
    const val = (r) => (r.cells[idx]?.innerText || "").trim();
    rows.sort((a, b) => {
      const x = val(a), y = val(b), nx = parseFloat(x.replace(/[$,]/g, "")), ny = parseFloat(y.replace(/[$,]/g, ""));
      const cmp = !isNaN(nx) && !isNaN(ny) ? nx - ny : x.localeCompare(y);
      return dir === "asc" ? cmp : -cmp;
    });
    rows.forEach((r) => tbody.appendChild(r));
  });
});
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
    const q = document.getElementById("q");
    if (q) { e.preventDefault(); q.focus(); }
  }
});
