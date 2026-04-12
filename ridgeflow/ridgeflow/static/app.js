const projectFilter = document.querySelector("[data-project-filter]");

if (projectFilter) {
  const cards = Array.from(document.querySelectorAll("[data-project-card]"));

  projectFilter.addEventListener("input", (event) => {
    const query = event.target.value.trim().toLowerCase();
    cards.forEach((card) => {
      const haystack = card.dataset.search || "";
      card.hidden = query.length > 0 && !haystack.includes(query);
    });
  });
}

const chatFeed = document.querySelector("[data-chat-feed]");
if (chatFeed) {
  chatFeed.scrollTop = chatFeed.scrollHeight;
}
