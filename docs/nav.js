// Shared site navigation, included on every resident-facing page via
// <script src="nav.js"></script>. One file so adding a future section
// (bulletin board, jobs board, artisans, volunteers, etc.) is a single
// edit to NAV_ITEMS below instead of touching every page on the site.
//
// Renders as a fixed bar (not squeezed into each page's own body/flex
// layout, which varies from page to page) plus a spacer element sized
// to match, so page content isn't hidden underneath it.
//
// Below NAV_BREAKPOINT, the list of items no longer fits in one row
// (11 items now, several multi-word) -- past that point, the row
// scrolled sideways with no visual hint it could, so entries like
// Survey/Contact were easy to miss entirely. Below the breakpoint this
// collapses behind a hamburger button into a vertical dropdown instead
// (Kevin's ask, 2026-09-17); above it, nothing changes from before.
(function () {
  const NAV_ITEMS = [
    { label: "Subscribe", href: "index.html" },
    { label: "Email Alerts", href: "alerts.html" },
    { label: "County Calendar", href: "calendar-view.html", children: [
      { label: "Submit Event", href: "submit.html" },
    ] },
    { label: "Business Directory", href: "directory.html", children: [
      { label: "List a Business or Service", href: "submit-business.html" },
    ] },
    { label: "Trading Post", href: "trading-post.html" },
    { label: "Jobs Bulletin", href: "jobs.html" },
    { label: "Lost & Found", href: "lost-found.html" },
    { label: "Flyer", href: "flyer.html" },
    { label: "Ideas for Your Town?", href: "survey.html" },
    { label: "Contact", href: "mailto:kevin@communitycalendarconnect.com" },
  ];
  const NAV_HEIGHT = "48px";
  const NAV_BREAKPOINT = "860px";

  const style = document.createElement("style");
  style.textContent = `
    .site-nav-bar {
      position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
      height: ${NAV_HEIGHT}; display: flex; align-items: stretch;
      background: var(--surface, #fff); border-bottom: 1px solid var(--surface-border, #e2e2e2);
    }
    .nav-toggle {
      display: none; flex-shrink: 0; align-items: center; justify-content: center;
      width: ${NAV_HEIGHT}; border: none; background: none; cursor: pointer;
      color: var(--ink, #1a1a1a); font-size: 1.3rem; line-height: 1; padding: 0;
    }
    /* No overflow-x:auto here above the breakpoint (the hamburger already
       covers cases where the row doesn't fit) -- a CSS quirk makes
       overflow-x:auto force overflow-y to auto too, which was silently
       clipping the Business Directory submenu below to nothing. */
    .site-nav {
      display: flex; align-items: stretch; flex: 1; min-width: 0;
      scrollbar-width: none;
    }
    .site-nav::-webkit-scrollbar { display: none; }
    /* The whole tab is one clickable box, but the only thing that ever
       showed that was a 3px underline -- easy to miss, and gave no
       feedback that a *click* (not just navigation) had landed (Kevin's
       catch, 2026-09-17: he assumed the text itself was somehow "dead"
       because the only visible reaction was that thin line). A
       background fill now covers the tab's full padded box, not just a
       sliver under the text, on hover, on press, and for whichever tab
       you're already on -- one accent color throughout, same blue used
       everywhere else on the site, not a different color per tab. */
    .site-nav a {
      flex-shrink: 0; display: flex; align-items: center;
      padding: 0 .9rem; font-size: .84rem; font-weight: 600; white-space: nowrap;
      letter-spacing: .01em;
      font-family: "Montserrat", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: var(--ink-soft, #555); text-decoration: none; border-bottom: 3px solid transparent;
      background: transparent; transition: background-color .1s ease, color .1s ease;
      -webkit-user-drag: none;
    }
    .site-nav a.active { color: var(--primary, #4285f4); border-bottom-color: var(--primary, #4285f4); background: rgba(123, 176, 247, .28); }
    .site-nav a:hover { color: var(--ink, #1a1a1a); background: rgba(127,127,127,.14); }
    .site-nav a.active:hover { background: rgba(123, 176, 247, .28); }
    .site-nav a:active { background: rgba(127,127,127,.28); }
    .site-nav-spacer { height: ${NAV_HEIGHT}; }
    /* A tab with a submenu (e.g. Business Directory -> List a Business or
       Service) -- the tab itself still navigates on click, the dropdown
       just appears on hover (or keyboard focus) as a bonus shortcut, so it
       has to still look and act like a plain nav tab, not a button. */
    .nav-item { position: relative; display: flex; align-items: stretch; }
    .nav-dropdown {
      display: none; position: absolute; top: 100%; left: 0; min-width: 230px;
      flex-direction: column; z-index: 1001;
      background: var(--surface, #fff); border: 1px solid var(--surface-border, #e2e2e2);
      border-top: none; border-radius: 0 0 8px 8px; box-shadow: 0 8px 16px rgba(0, 0, 0, .15);
    }
    .nav-item:hover .nav-dropdown, .nav-item:focus-within .nav-dropdown { display: flex; }
    .nav-dropdown a { border-bottom: none; padding: .75rem 1rem; }
    @media (max-width: ${NAV_BREAKPOINT}) {
      .nav-toggle { display: flex; }
      .site-nav {
        display: none; position: fixed; top: ${NAV_HEIGHT}; left: 0; right: 0;
        flex-direction: column; overflow-x: visible; overflow-y: auto;
        -webkit-overflow-scrolling: touch;
        max-height: calc(100vh - ${NAV_HEIGHT});
        background: var(--surface, #fff); border-bottom: 1px solid var(--surface-border, #e2e2e2);
        box-shadow: 0 8px 16px rgba(0, 0, 0, .15);
      }
      .site-nav.open { display: flex; }
      .site-nav a {
        padding: .9rem 1.1rem; border-bottom: 1px solid var(--surface-border, #e2e2e2);
        border-left: 3px solid transparent;
      }
      .site-nav a.active { border-left-color: var(--primary, #4285f4); border-bottom-color: var(--surface-border, #e2e2e2); }
      /* No hover on touch -- the submenu is just always open, indented
         under its parent, right in the vertical stack. */
      .nav-item { flex-direction: column; }
      .nav-dropdown {
        display: flex; position: static; min-width: 0; border: none; box-shadow: none;
      }
      .nav-dropdown a { padding-left: 2.4rem; font-weight: 500; }
    }
    @media print {
      .site-nav-bar, .site-nav-spacer { display: none !important; }
    }
  `;
  document.head.appendChild(style);

  const currentFile = location.pathname.split("/").pop() || "index.html";

  function makeLink(item) {
    const a = document.createElement("a");
    a.href = item.href;
    a.textContent = item.label;
    // Links/text are natively draggable in the browser -- the tiniest bit
    // of mouse movement during a click (routine with a trackpad) can get
    // read as starting a drag instead of a click, which cancels the
    // click and shows the browser's own translucent drag-ghost of the
    // link instead of navigating (Kevin's catch, 2026-09-17: "a smaller
    // square, kind of faded... doesn't take me to that tab"). Only
    // happened when the cursor was over the text itself, never the
    // padding around it, because that's exactly what's draggable.
    a.draggable = false;
    if (item.external) {
      a.target = "_blank";
      a.rel = "noopener";
    } else if (item.href.split("/").pop() === currentFile) {
      a.classList.add("active");
      a.setAttribute("aria-current", "page");
    }
    return a;
  }

  const nav = document.createElement("nav");
  nav.className = "site-nav";
  nav.setAttribute("aria-label", "Site navigation");
  for (const item of NAV_ITEMS) {
    if (item.children && item.children.length) {
      const wrap = document.createElement("div");
      wrap.className = "nav-item";

      const a = makeLink(item);
      wrap.appendChild(a);

      const dropdown = document.createElement("div");
      dropdown.className = "nav-dropdown";
      for (const child of item.children) {
        const childLink = makeLink(child);
        dropdown.appendChild(childLink);
        // Being on the child page (e.g. submit-business.html) highlights
        // the parent tab too, same as any other tab shows you where you are.
        if (child.href.split("/").pop() === currentFile) {
          a.classList.add("active");
        }
      }
      wrap.appendChild(dropdown);
      nav.appendChild(wrap);
    } else {
      nav.appendChild(makeLink(item));
    }
  }

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "nav-toggle";
  toggle.setAttribute("aria-label", "Menu");
  toggle.setAttribute("aria-expanded", "false");
  toggle.textContent = "☰"; // ☰

  function closeMenu() {
    nav.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
  }
  toggle.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
  // Any link tap closes the dropdown -- most links navigate away anyway
  // (which clears this state on its own), but a mailto one (Contact)
  // doesn't leave the page, so it'd otherwise stay open over whatever
  // the visitor does next.
  nav.addEventListener("click", (e) => {
    if (e.target.tagName === "A") closeMenu();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeMenu();
  });
  // Tapping anywhere outside the open dropdown (or its toggle) closes it.
  document.addEventListener("click", (e) => {
    if (nav.classList.contains("open") && !nav.contains(e.target) && e.target !== toggle) {
      closeMenu();
    }
  });

  const bar = document.createElement("div");
  bar.className = "site-nav-bar";
  bar.appendChild(toggle);
  bar.appendChild(nav);

  const spacer = document.createElement("div");
  spacer.className = "site-nav-spacer";

  document.body.insertBefore(spacer, document.body.firstChild);
  document.body.insertBefore(bar, document.body.firstChild);
})();
