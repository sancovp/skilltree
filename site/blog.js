// The Hive Log — render the blog series from blog.json.
// Index view (no hash) lists posts; #slug renders one post. Posts carry HTML bodies.

function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}

let POSTS = [];

function renderIndex() {
  const idx = document.getElementById("index");
  const post = document.getElementById("post");
  post.hidden = true; idx.hidden = false;
  idx.innerHTML = "";
  POSTS.forEach((p, i) => {
    const card = el("a", "blogcard");
    card.href = `#${p.slug}`;
    card.appendChild(el("div", "bnum", `#${String(i + 1).padStart(2, "0")}`));
    card.appendChild(el("h3", null, p.title));
    card.appendChild(el("p", "dek", p.dek || ""));
    const meta = el("p", "bmeta", `${p.author} · ${p.date}`);
    if (p.tags) p.tags.forEach(t => meta.appendChild(el("span", "tag", t)));
    card.appendChild(meta);
    idx.appendChild(card);
  });
}

function renderPost(slug) {
  const p = POSTS.find(x => x.slug === slug);
  if (!p) { location.hash = ""; return; }
  const idx = document.getElementById("index");
  const post = document.getElementById("post");
  idx.hidden = true; post.hidden = false;
  const i = POSTS.indexOf(p);
  const prev = POSTS[i - 1], next = POSTS[i + 1];
  post.innerHTML = "";
  post.appendChild(el("p", "nav", `<a href="#">← all posts</a>`));
  post.appendChild(el("div", "bnum", `#${String(i + 1).padStart(2, "0")}`));
  post.appendChild(el("h2", "ptitle", p.title));
  post.appendChild(el("p", "bmeta", `${p.author} · ${p.date}`));
  post.appendChild(el("div", "pbody", p.html));
  const navp = el("div", "pnav");
  if (prev) navp.appendChild(el("a", "pnav-l", `← ${prev.title}`)).href = `#${prev.slug}`;
  if (next) navp.appendChild(el("a", "pnav-r", `${next.title} →`)).href = `#${next.slug}`;
  post.appendChild(navp);
  window.scrollTo(0, 0);
}

function route() {
  const slug = location.hash.replace(/^#/, "");
  if (slug) renderPost(slug); else renderIndex();
}

async function main() {
  try {
    POSTS = await (await fetch("blog.json", { cache: "no-store" })).json();
    window.addEventListener("hashchange", route);
    route();
  } catch (err) {
    document.getElementById("index").innerHTML =
      `<p class="dek">Could not load <code>blog.json</code> (${err}).</p>`;
  }
}
main();
