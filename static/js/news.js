async function loadNews() {
  const newsEl = document.getElementById("news-list");
  const sourcesEl = document.getElementById("sources-list");

  newsEl.innerHTML = "<p>Loading...</p>";
  try {
    const res = await fetch("/api/news");
    const data = await res.json();

    newsEl.innerHTML = "";
    (data.items || []).forEach(item => {
      const div = document.createElement("div");
      div.className = "item";
      div.innerHTML = `
        <h3>${item.headline ?? "Untitled"}</h3>
        <p>${item.summary ?? ""}</p>
        ${item.link ? `<p class="link"><a href="${item.link}" target="_blank" rel="noopener">Open article</a></p>` : ""}
      `;
      newsEl.appendChild(div);
    });

    sourcesEl.innerHTML = "";
    (data.sources || []).forEach(url => {
      const li = document.createElement("li");
      li.innerHTML = `<a href="${url}" target="_blank" rel="noopener">${url}</a>`;
      sourcesEl.appendChild(li);
    });
  } catch (e) {
    newsEl.innerHTML = `<p>Failed to load news. ${e}</p>`;
  }
}

loadNews();