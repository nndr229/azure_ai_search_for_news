async function loadSources() {
  const list = document.getElementById("sources-agg");
  list.innerHTML = "<li>Loading...</li>";
  try {
    const res = await fetch("/api/sources");
    const data = await res.json();
    list.innerHTML = "";
    (data.sources || []).forEach(s => {
      const li = document.createElement("li");
      li.innerHTML = `[${s.from}] <a href="${s.url}" target="_blank" rel="noopener">${s.url}</a>`;
      list.appendChild(li);
    });
  } catch (e) {
    list.innerHTML = `<li>Failed to load sources. ${e}</li>`;
  }
}
loadSources();