// Shared site navigation, included on every resident-facing page via
// <script src="nav.js"></script>. One file so adding a future section
// (bulletin board, jobs board, artisans, volunteers, etc.) is a single
// edit to NAV_ITEMS below instead of touching every page on the site.
//
// Renders as a fixed bar (not squeezed into each page's own body/flex
// layout, which varies from page to page) plus a spacer element sized
// to match, so page content isn't hidden underneath it.
(function () {
  const NAV_ITEMS = [
    { label: "Subscribe", href: "index.html" },
    { label: "Email Alerts", href: "alerts.html" },
    { label: "Calendar", href: "calendar-view.html" },
    { label: "Submit Event", href: "submit.html" },
    { label: "Flyer", href: "flyer.html" },
    { label: "Survey", href: "https://forms.gle/ABFjuyF43CoUqHoF7", external: true },
    { label: "Contact", href: "mailto:kevin@communitycalendarconnect.com" },
  ];
  const NAV_HEIGHT = "48px";

  const style = document.createElement("style");
  style.textContent = `
    .site-nav {
      position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
      height: ${NAV_HEIGHT}; display: flex; align-items: stretch;
      overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: none;
      background: var(--surface, #fff); border-bottom: 1px solid var(--surface-border, #e2e2e2);
    }
    .site-nav::-webkit-scrollbar { display: none; }
    .site-nav a {
      flex-shrink: 0; display: flex; align-items: center;
      padding: 0 .9rem; font-size: .84rem; font-weight: 600; white-space: nowrap;
      letter-spacing: .01em;
      font-family: "Montserrat", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: var(--ink-soft, #555); text-decoration: none; border-bottom: 3px solid transparent;
    }
    .site-nav a.active { color: var(--primary, #4285f4); border-bottom-color: var(--primary, #4285f4); }
    .site-nav a:hover { color: var(--ink, #1a1a1a); }
    .site-nav-spacer { height: ${NAV_HEIGHT}; }
    @media print {
      .site-nav, .site-nav-spacer { display: none !important; }
    }
  `;
  document.head.appendChild(style);

  const currentFile = location.pathname.split("/").pop() || "index.html";

  const nav = document.createElement("nav");
  nav.className = "site-nav";
  nav.setAttribute("aria-label", "Site navigation");
  for (const item of NAV_ITEMS) {
    const a = document.createElement("a");
    a.href = item.href;
    a.textContent = item.label;
    if (item.external) {
      a.target = "_blank";
      a.rel = "noopener";
    } else if (item.href.split("/").pop() === currentFile) {
      a.classList.add("active");
      a.setAttribute("aria-current", "page");
    }
    nav.appendChild(a);
  }

  const spacer = document.createElement("div");
  spacer.className = "site-nav-spacer";

  document.body.insertBefore(spacer, document.body.firstChild);
  document.body.insertBefore(nav, document.body.firstChild);
})();
