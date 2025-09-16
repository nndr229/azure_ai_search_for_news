async function loadImprovements() {
  const listEl = document.getElementById("improvements-list");
  const sourcesEl = document.getElementById("sources-list");

  listEl.innerHTML = "<p>Loading...</p>";
  try {
    const res = await fetch("/api/improvements");
    const data = await res.json();

    listEl.innerHTML = "";
    (data.items || []).forEach(item => {
      const div = document.createElement("div");
      div.className = "item";
      div.innerHTML = `
        <h3>${item.headline ?? "Untitled"}</h3>
        <p>${item.summary ?? ""}</p>
        ${item.why ? `<p><strong>Why it matters:</strong> ${item.why}</p>` : ""}
        ${item.link ? `<p class="link"><a href="${item.link}" target="_blank" rel="noopener">Read documentation</a></p>` : ""}
      `;
      listEl.appendChild(div);
    });

    sourcesEl.innerHTML = "";
    (data.sources || []).forEach(url => {
      const li = document.createElement("li");
      li.innerHTML = `<a href="${url}" target="_blank" rel="noopener">${url}</a>`;
      sourcesEl.appendChild(li);
    });
  } catch (e) {
    listEl.innerHTML = `<p>Failed to load improvements. ${e}</p>`;
  }
}

loadImprovements();