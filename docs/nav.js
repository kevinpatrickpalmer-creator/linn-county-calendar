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
    { label: "County Calendar", href: "calendar-view.html", dot: "--sec-calendar", children: [
      { label: "Subscribe", href: "subscribe.html" },
      { label: "Email Alerts", href: "alerts.html" },
      { label: "Submit Event", href: "submit.html" },
    ] },
    { label: "Business Directory", href: "directory.html", dot: "--sec-directory", children: [
      { label: "List a Business or Service", href: "submit-business.html" },
    ] },
    { label: "Trading Post", href: "trading-post.html", dot: "--sec-trading-post", children: [
      { label: "List Something", href: "submit-trading-post.html" },
    ] },
    { label: "Jobs Bulletin", href: "jobs.html", dot: "--sec-jobs", children: [
      { label: "Post to the Bulletin", href: "submit-job.html" },
    ] },
    { label: "Volunteer & Help Needed", href: "volunteer.html", dot: "--sec-volunteer", children: [
      { label: "Post a Volunteer Need", href: "submit-volunteer.html" },
    ] },
    { label: "Clubs & Classes", href: "clubs.html", dot: "--sec-clubs", children: [
      { label: "Post a Club or Class", href: "submit-clubs.html" },
    ] },
    { label: "Lost & Found", href: "lost-found.html", dot: "--sec-lost-found", children: [
      { label: "Post to Lost & Found", href: "submit-lost-found.html" },
    ] },
    { label: "Ask the Community", href: "ask-community.html", dot: "--sec-ask", children: [
      { label: "Ask a Question", href: "submit-question.html" },
    ] },
    { label: "Notices", href: "notices.html", dot: "--sec-notices", children: [
      { label: "Post a Notice", href: "submit-notice.html" },
    ] },
    { label: "Community Support", href: "support.html", dot: "--sec-support", children: [
      { label: "Post to Community Support", href: "submit-support.html" },
    ] },
    { label: "Local Alerts", href: "local-alerts.html", dot: "--sec-alerts", children: [
      { label: "Post a Local Alert", href: "submit-alert.html" },
    ] },
    { label: "Print Flyer", href: "flyer.html", dot: "--sec-flyer" },
    { label: "Big Idea Board", href: "big-ideas.html", dot: "--sec-ideas", children: [
      { label: "Submit Idea", href: "submit-idea.html" },
    ] },
    // Was "Survey" -- dropped from the nav at some point (Kevin's catch,
    // 2026-09-27), re-added under a warmer label instead of restoring
    // the old one: "suggestion box" reads like a small-town fixture,
    // "survey" reads like market research. Points at its own page now
    // (docs/suggestion-box.html), not the old community-needs survey
    // (docs/survey.html, still linked from a couple of other pages) --
    // Kevin's follow-up, 2026-09-27: this is specifically for website
    // ideas and bug reports, a narrower job than that longer survey, and
    // distinct from Contact, which he wants reserved for business/
    // official inquiries. Private form to Kevin, not a public board, so
    // no --sec-* color of its own, same as Contact.
    { label: "Suggestion Box", href: "suggestion-box.html" },
    { label: "Contact", href: "contact.html" },
  ];
  const NAV_HEIGHT = "48px";
  const NAV_BREAKPOINT = "860px";

  const style = document.createElement("style");
  style.textContent = `
    /* Bold solid-color bar (Kevin's ask, 2026-09-24: "copy that header
       look" from a reference screenshot's bright yellow app header --
       trying the actual yellow this time, not just the "bold bar"
       concept) instead of plain white. Dark ink text/icons here since
       yellow needs dark-on-light, not light-on-dark like the earlier
       blue version -- see .site-nav a below for how tab text stays
       legible against it, and the mobile breakpoint further down for
       why the dropdown panel goes back to white once open. */
    .site-nav-bar {
      position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
      min-height: ${NAV_HEIGHT}; display: flex; align-items: stretch;
      background: var(--sec-lost-found, #ffd23f);
      /* 4px to match every card's own border weight (Kevin's ask,
         2026-09-24: "gives it thickness and weight and matches the
         cards"), up from the original plain 3px divider. */
      border-bottom: 4px solid var(--surface-border, #1a1a1a);
    }
    .site-brand {
      flex-shrink: 0; display: flex; align-items: center; gap: .6rem;
      padding: .3rem .9rem; white-space: nowrap;
      color: var(--ink, #1a1a1a); text-decoration: none; -webkit-user-drag: none;
      border-right: 1px solid rgba(0,0,0,.15);
    }
    /* White square, not the black one from the first pass (Kevin's
       catch, 2026-09-24: he never asked for the badge stuffed into a
       small black box, and wanted the logo to actually fill the tile).
       White matches the exact .mo-badge treatment used everywhere else
       on the site (hero, every submit page) -- same white circle, black
       border, badge sitting directly on it -- so this reuses a color
       the badge is already designed to sit on, rather than inventing a
       new background for it. That also rules out blue here: the badge's
       own accent color is a light blue (#7bb0f7), which would nearly
       disappear against a light blue tile. Padding cut down and the box
       sized up so the badge actually fills it, doubling as an obvious
       home icon, instead of sitting small and centered with room to
       spare. Border keeps it visually distinct from the yellow bar. */
    .site-brand .brand-icon {
      width: 48px; height: 48px; flex-shrink: 0;
      background: #fff;
      border: 3px solid var(--surface-border, #1a1a1a);
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      padding: 3px;
    }
    .site-brand .brand-icon img { width: 100%; height: 100%; display: block; }
    /* Each word its own line -- Kevin's ask, 2026-09-24: "linn county
       local should be stacked ... reading vertically rather than
       horizontally" -- like a small seal/badge next to the icon square
       rather than a wide single-line wordmark. Bar has min-height (not
       a fixed height) precisely so it can grow to fit this. */
    .site-brand .brand-text {
      display: flex; flex-direction: column;
      font-size: .82rem; line-height: 1.05; font-weight: 800;
      letter-spacing: .01em;
      font-family: var(--font-display, "Montserrat", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif);
    }
    .site-brand:hover .brand-text { color: var(--primary, #2f6fed); }
    .nav-toggle {
      display: none; flex-shrink: 0; align-items: center; justify-content: center;
      width: ${NAV_HEIGHT}; border: none; background: none; cursor: pointer;
      color: var(--ink, #1a1a1a); font-size: 1.3rem; line-height: 1; padding: 0;
    }
    /* No overflow-x:auto here above the breakpoint (the hamburger already
       covers cases where the row doesn't fit below it) -- a CSS quirk
       makes overflow-x:auto force overflow-y to auto too, which was
       silently clipping the Business Directory submenu below to nothing.
       Above the breakpoint, a row that still doesn't fit (more tabs than
       a given screen has room for, even though it's wider than the
       breakpoint) wraps onto a second line instead -- items were
       silently overflowing past the edge of the screen with no way to
       reach them at all once there were enough tabs to not fit even a
       1280-1400px laptop window (Kevin's catch, 2026-09-21). The bar
       itself has min-height, not a fixed height, so it grows to fit
       either row count; JS below keeps the spacer in sync with however
       tall that ends up being. */
    /* A real grid, not flex-wrap (Kevin's catch, 2026-09-27: with tabs of
       very different label lengths, flex-wrap packs each row tight
       against its own content, so row 2's tabs don't line up under
       row 1's at all -- it reads as scattered rather than a tidy block).
       auto-fill with a minmax column keeps every row on the same column
       grid regardless of width, and lets the column count itself shrink
       as the window narrows, all the way down to the hamburger
       breakpoint below. */
    .site-nav {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
      align-items: stretch; flex: 1; min-width: 0;
      gap: .5rem; padding: .5rem .75rem;
      scrollbar-width: none;
    }
    .site-nav::-webkit-scrollbar { display: none; }
    /* Each tab is its own bordered rectangular button (Kevin's ask,
       2026-09-24, from a reference screenshot: two bordered buttons next
       to a header, one white, one filled -- "id like the menu tabs to
       look like those"), permanently filled with that section's own
       --sec-* color (Kevin's follow-up ask, 2026-09-24: "the calendar
       card is blue so the tab in the menu should be blue") -- same color
       as that page's homepage card, set via --tab-accent below, so
       "this page is blue" is true everywhere all the time, not just
       while you're on it. Flyer/Contact have no card or color of their
       own, so --tab-accent falls back to white for them specifically
       (see makeLink below). The tab for the page you're actually on is
       marked by sitting "pressed in" (no shadow, tucked under where its
       shadow would be) instead of a color change, since color no longer
       has a spare state left to encode that with everything already
       colored. */
    .site-nav a {
      display: flex; align-items: center; justify-content: center; min-height: 0;
      padding: .5rem .95rem; font-size: .84rem; font-weight: 700; text-align: center;
      letter-spacing: .01em; line-height: 1.2;
      font-family: var(--font-body, "Montserrat", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif);
      color: var(--ink, #1a1a1a); text-decoration: none;
      background: var(--tab-accent, #fff); border: 3px solid var(--surface-border, #1a1a1a); border-radius: 9px;
      box-shadow: var(--shadow-sm); transition: transform .12s ease, box-shadow .1s ease;
      -webkit-user-drag: none;
    }
    .site-nav a:hover { transform: translate(-2px, -2px); }
    .site-nav a:active { transform: translate(0, 0); }
    .site-nav a.active {
      box-shadow: none;
      transform: translate(4px, 4px);
    }
    .site-nav-spacer { height: ${NAV_HEIGHT}; }
    /* A tab with a submenu (e.g. Business Directory -> List a Business or
       Service) -- the tab itself still navigates on click, the dropdown
       just appears on hover (or keyboard focus) as a bonus shortcut, so it
       has to still look and act like a plain nav tab, not a button. */
    .nav-item { position: relative; display: flex; align-items: stretch; width: 100%; }
    .nav-item > a { flex: 1; }
    .nav-dropdown {
      display: none; position: absolute; top: 100%; left: 0; min-width: 230px;
      flex-direction: column; z-index: 1001;
      background: var(--surface, #fff); border: 1px solid var(--surface-border, #e2e2e2);
      border-top: none; border-radius: 0 0 8px 8px; box-shadow: 0 8px 16px rgba(0, 0, 0, .15);
    }
    .nav-item:hover .nav-dropdown, .nav-item:focus-within .nav-dropdown { display: flex; }
    /* Its own white floating panel, same reasoning as the mobile
       dropdown below -- reset color back to dark since the white-on-
       blue tab text above would be invisible against it. */
    .nav-dropdown a { color: var(--ink-soft, #555); border-bottom: none; padding: .75rem 1rem; }
    .nav-dropdown a:hover { color: var(--ink, #1a1a1a); }
    @media (max-width: ${NAV_BREAKPOINT}) {
      .nav-toggle { display: flex; }
      .site-nav {
        display: none; position: fixed; top: ${NAV_HEIGHT}; left: 0; right: 0;
        /* flex-wrap:nowrap overrides the desktop row-wrap rule above --
           without this, a column this tall wraps into a second column
           instead of just scrolling, once it's taller than max-height. */
        flex-direction: column; flex-wrap: nowrap; overflow-x: visible; overflow-y: auto;
        -webkit-overflow-scrolling: touch;
        max-height: calc(100vh - ${NAV_HEIGHT});
        background: var(--surface, #fff); border-bottom: 1px solid var(--surface-border, #e2e2e2);
        box-shadow: 0 8px 16px rgba(0, 0, 0, .15);
      }
      .site-nav.open { display: flex; }
      /* The open dropdown panel is its own white surface below the bar,
         not the bar itself -- text/dots reset back to the original
         light-theme colors here, since the desktop button treatment
         above (border, shadow, per-section fill) is for the horizontal
         bar only and doesn't belong in this stacked list. */
      .site-nav a {
        color: var(--ink-soft, #555); border-bottom: 1px solid var(--surface-border, #e2e2e2);
        background: transparent; border-left: 3px solid transparent;
        border-top: none; border-right: none; border-radius: 0; box-shadow: none;
        padding: .9rem 1.1rem; transform: none;
      }
      .site-nav a.active {
        color: var(--primary, #2f6fed); background: var(--primary-tint, #eaf1ff);
        border-left-color: var(--primary, #2f6fed); border-bottom-color: var(--surface-border, #e2e2e2);
      }
      .site-nav a:hover { color: var(--ink, #1a1a1a); background: rgba(127,127,127,.14); transform: none; }
      .site-nav a.active:hover { background: var(--primary-tint, #eaf1ff); }
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
    // item.dot is a CSS custom property name (see the --sec-* palette in
    // theme.css). Contact is the only item left with no color of its own
    // (stays white) -- Flyer has one too now (a muted grey, since it
    // still has no homepage card to match, unlike the 11 real sections).
    a.style.setProperty("--tab-accent", item.dot ? `var(${item.dot})` : "#fff");
    a.appendChild(document.createTextNode(item.label));
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
  // (which clears this state on its own), but a mailto/external one
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

  const brand = document.createElement("a");
  brand.className = "site-brand";
  brand.href = "index.html";
  brand.draggable = false;
  brand.innerHTML = `<span class="brand-icon" aria-hidden="true"><img src="logo-badge.svg" alt=""></span><span class="brand-text"><span>Linn</span><span>County</span><span>Local</span></span>`;

  const bar = document.createElement("div");
  bar.className = "site-nav-bar";
  bar.appendChild(brand);
  bar.appendChild(toggle);
  bar.appendChild(nav);

  const spacer = document.createElement("div");
  spacer.className = "site-nav-spacer";

  document.body.insertBefore(spacer, document.body.firstChild);
  document.body.insertBefore(bar, document.body.firstChild);

  // The spacer's CSS height is just a same-as-NAV_HEIGHT fallback for
  // before this runs -- once the bar can wrap onto a second row (see
  // .site-nav's flex-wrap above), its real height varies with viewport
  // width and how many tabs fit per row, so the spacer has to track it
  // directly rather than assume one fixed number. ResizeObserver instead
  // of a window resize listener because a wrap can also be triggered by
  // things that change without the window itself resizing (a page's own
  // fonts loading in, an aria-expanded submenu, browser zoom).
  const syncSpacerHeight = () => { spacer.style.height = bar.offsetHeight + "px"; };
  if (window.ResizeObserver) {
    new ResizeObserver(syncSpacerHeight).observe(bar);
  } else {
    syncSpacerHeight();
    window.addEventListener("resize", syncSpacerHeight);
  }
})();

// Counts a visit once per browser (a localStorage flag, not a real
// fingerprint -- "unique" here means "unique browser that hasn't set
// the flag before," which is what a small-town site showing "people are
// using this" needs, not analytics-grade dedup) and exposes the
// county-wide running total for any page to display -- currently just
// docs/index.html, via window.linnVisitCountReady. Runs on every page
// since a visitor can land anywhere first, not just the homepage, but
// only ever increments the shared total the first time a given browser
// is seen, regardless of which page that happens on.
(function () {
  const FLAG_KEY = "lcl_visited";
  let alreadyVisited = false;
  try {
    alreadyVisited = localStorage.getItem(FLAG_KEY) === "1";
  } catch (err) {
    // Private browsing / blocked storage -- treat as already-visited so
    // a browser that can't remember never gets counted more than once
    // by accident on repeat page loads within the same session.
    alreadyVisited = true;
  }

  window.linnVisitCountReady = (async () => {
    try {
      const config = await (await fetch("config.json")).json();
      const res = await fetch(config.apps_script_api_url, {
        method: "POST",
        body: JSON.stringify({ action: "recordVisit", increment: !alreadyVisited }),
      });
      const result = await res.json();
      if (!alreadyVisited && result.success) {
        try { localStorage.setItem(FLAG_KEY, "1"); } catch (err) {}
      }
      return result.success ? result.count : null;
    } catch (err) {
      return null;
    }
  })();
})();
