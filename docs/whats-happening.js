// "What's Happening Now" homepage ticker -- pulls live from every board's
// already-published feed (the same JSON each board's own page reads),
// the calendar ICS, and the Big Idea Board's live API, then merges them
// into one ranked list and renders it into #whList on index.html.
//
// No build step of its own: as real posts replace example content on any
// board, they show up here automatically, nothing to rebuild as content
// grows. Example/seed content is filtered out everywhere (item.example),
// this is meant to show what's actually happening, not sample data.
//
// Evergreen catalogs (Trading Post, Business Directory) are deliberately
// left out -- they're "browse anytime," not "just happened," so they
// don't belong in a feed about what's fresh.

(function () {
  const MAX_ITEMS = 8;
  const MAX_UPCOMING_EVENTS = 6;

  function relTime(iso) {
    const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
    if (days <= 0) return "today";
    if (days === 1) return "yesterday";
    if (days < 14) return `${days} days ago`;
    const weeks = Math.floor(days / 7);
    return `${weeks} week${weeks === 1 ? "" : "s"} ago`;
  }

  function eventWhen(date) {
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const days = Math.round((date - startOfToday) / 86400000);
    if (days === 0) return "Today";
    if (days === 1) return "Tomorrow";
    if (days > 1 && days < 7) return new Intl.DateTimeFormat("en-US", { weekday: "long" }).format(date);
    return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(date);
  }

  function truncate(text, max) {
    if (!text) return "";
    return text.length > max ? text.slice(0, max - 1).trim() + "…" : text;
  }

  function unescapeText(s) {
    return s.replace(/\\n/gi, " ").replace(/\\,/g, ",").replace(/\\;/g, ";").replace(/\\\\/g, "\\");
  }

  function parseICSDate(value, isDateOnly) {
    const y = value.slice(0, 4), m = value.slice(4, 6), d = value.slice(6, 8);
    if (isDateOnly) return new Date(`${y}-${m}-${d}T00:00:00`);
    const hh = value.slice(9, 11), mm = value.slice(11, 13), ss = value.slice(13, 15);
    return new Date(`${y}-${m}-${d}T${hh}:${mm}:${ss}Z`);
  }

  // Mirrors extractTown()/extractExtraTowns() in calendar-view.html --
  // LOCATION reads "District Name | Town, ST", and a title can also name
  // a second county town on its own (an intra-county matchup, now that
  // sports titles spell out both teams, e.g. "Softball: Linn County R-I
  // at Meadville" where Meadville is itself one of the 8 towns). Kept in
  // sync by hand with the same fields calendar-view.html reads.
  function extractTown(location, state, towns) {
    if (!location) return "";
    const lastSegment = location.split("|").pop().trim();
    const m = lastSegment.match(new RegExp(`([A-Za-z .]+?),\\s*${state}\\b`));
    const town = m ? m[1].trim() : "";
    return town && towns.includes(town) ? town : "";
  }
  function extractExtraTowns(summary, primaryTown, towns) {
    if (!summary) return [];
    return towns.filter((town) => town !== primaryTown && new RegExp(`\\b${town}\\b`, "i").test(summary));
  }

  // Trimmed down from calendar-view.html's parseICS -- this ticker only
  // needs SUMMARY, LOCATION, and DTSTART, not the category machinery
  // the full calendar view uses for filtering.
  function parseUpcomingEvents(raw, state, towns) {
    const unfolded = raw.replace(/\r\n[ \t]/g, "").replace(/\n[ \t]/g, "");
    const lines = unfolded.split(/\r?\n/);
    const events = [];
    let current = null;
    for (const line of lines) {
      if (line === "BEGIN:VEVENT") { current = {}; continue; }
      if (line === "END:VEVENT") {
        if (current && current.summary && current.start) events.push(current);
        current = null;
        continue;
      }
      if (!current) continue;
      const colonIdx = line.indexOf(":");
      if (colonIdx === -1) continue;
      const rawKey = line.slice(0, colonIdx);
      const value = line.slice(colonIdx + 1);
      const key = rawKey.split(";")[0];
      const isDateOnly = rawKey.includes("VALUE=DATE");
      if (key === "SUMMARY") current.summary = unescapeText(value);
      if (key === "LOCATION") current.location = unescapeText(value);
      if (key === "DTSTART") { current.start = parseICSDate(value, isDateOnly); current.allDay = isDateOnly; }
    }
    for (const ev of events) {
      const town = extractTown(ev.location, state, towns);
      ev.towns = [town, ...extractExtraTowns(ev.summary, town, towns)].filter(Boolean);
    }
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return events
      .filter((ev) => ev.start >= startOfToday)
      .sort((a, b) => a.start - b.start)
      .slice(0, MAX_UPCOMING_EVENTS);
  }

  async function fetchBoard(url) {
    try {
      const res = await fetch(url);
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data) ? data.filter((item) => !item.example) : [];
    } catch (err) {
      return [];
    }
  }

  async function fetchIdeas(apiUrl) {
    if (!apiUrl) return [];
    try {
      const res = await fetch(`${apiUrl}?action=list`);
      const result = await res.json();
      return (result.ideas || []).filter((idea) => !idea.example);
    } catch (err) {
      return [];
    }
  }

  function boardItems(list, dotVar, label, href, toText, toMeta) {
    return list.map((item) => ({
      dotVar,
      label,
      href,
      text: toText(item),
      meta: toMeta(item),
      sortDate: new Date(item.posted || item.submitted),
    }));
  }

  async function main() {
    const section = document.getElementById("whatsHappening");
    const listEl = document.getElementById("whList");
    if (!section || !listEl) return;

    let config = {};
    try { config = await (await fetch("config.json")).json(); } catch (err) {}

    const [icsText, jobs, notices, volunteer, lostFound, clubs, questions, support, alerts, ideas] =
      await Promise.all([
        fetch("linn_county_events.ics").then((r) => (r.ok ? r.text() : "")).catch(() => ""),
        fetchBoard("jobs.json"),
        fetchBoard("notices.json"),
        fetchBoard("volunteer.json"),
        fetchBoard("lost-found.json"),
        fetchBoard("clubs.json"),
        fetchBoard("questions.json"),
        fetchBoard("support.json"),
        fetchBoard("local-alerts.json"),
        fetchIdeas(config.apps_script_api_url),
      ]);

    const items = [];

    if (icsText) {
      const towns = config.towns || [];
      for (const ev of parseUpcomingEvents(icsText, config.state, towns)) {
        const when = eventWhen(ev.start);
        items.push({
          dotVar: "--sec-calendar",
          label: "Calendar",
          href: "calendar-view.html",
          text: truncate(ev.summary, 70),
          meta: ev.towns.length ? `${when} · ${ev.towns.join(" & ")}` : when,
          sortDate: ev.start,
        });
      }
    }

    items.push(...boardItems(jobs, "--sec-jobs", "Jobs Bulletin", "jobs.html",
      (i) => i.category,
      (i) => `${i.type === "offering" ? "Offering work" : "Looking for work"} · ${i.town} · ${relTime(i.posted)}`));

    items.push(...boardItems(notices, "--sec-notices", "Notices", "notices.html",
      (i) => truncate(i.message, 80),
      (i) => `${i.town} · ${relTime(i.posted)}`));

    items.push(...boardItems(volunteer, "--sec-volunteer", "Volunteer & Help Needed", "volunteer.html",
      (i) => i.category,
      (i) => `${i.type === "needed" ? "Volunteers needed" : "Help offered"} · ${i.town} · ${relTime(i.posted)}`));

    items.push(...boardItems(lostFound, "--sec-lost-found", "Lost & Found", "lost-found.html",
      (i) => truncate(i.name, 70),
      (i) => `${i.type === "lost" ? "Lost" : "Found"} · ${i.town} · ${relTime(i.posted)}`));

    items.push(...boardItems(clubs, "--sec-clubs", "Clubs & Classes", "clubs.html",
      (i) => i.name,
      (i) => `${i.category} · ${i.town} · ${relTime(i.posted)}`));

    items.push(...boardItems(questions, "--sec-ask", "Ask the Community", "ask-community.html",
      (i) => truncate(i.question, 80),
      (i) => `${i.town} · ${relTime(i.posted)}`));

    items.push(...boardItems(support, "--sec-support", "Community Support", "support.html",
      (i) => i.name,
      (i) => `${i.type === "needed" ? "Needed" : "Offering"} · ${i.category} · ${relTime(i.posted)}`));

    items.push(...boardItems(alerts, "--sec-alerts", "Local Alerts", "local-alerts.html",
      (i) => truncate(i.message, 80),
      (i) => `${i.town} · ${relTime(i.posted)}`));

    items.push(...boardItems(ideas, "--sec-ideas", "Big Idea Board", "big-ideas.html",
      (i) => i.title,
      (i) => `${i.town ? i.town + " · " : ""}${relTime(i.submitted)}`));

    if (!items.length) return; // section stays hidden, no awkward empty state

    const now = Date.now();
    items.sort((a, b) => Math.abs(a.sortDate - now) - Math.abs(b.sortDate - now));

    for (const item of items.slice(0, MAX_ITEMS)) {
      const a = document.createElement("a");
      a.className = "wh-item";
      a.href = item.href;

      const dot = document.createElement("span");
      dot.className = "wh-dot";
      dot.style.background = `var(${item.dotVar})`;
      dot.setAttribute("aria-hidden", "true");

      const body = document.createElement("div");
      body.className = "wh-body";
      const tag = document.createElement("div");
      tag.className = "wh-tag";
      tag.style.color = `var(${item.dotVar})`;
      tag.textContent = item.label;
      const text = document.createElement("div");
      text.className = "wh-text";
      text.textContent = item.text;
      const meta = document.createElement("div");
      meta.className = "wh-meta";
      meta.textContent = item.meta;
      body.appendChild(tag);
      body.appendChild(text);
      body.appendChild(meta);

      a.appendChild(dot);
      a.appendChild(body);
      listEl.appendChild(a);
    }

    section.style.display = "";
  }

  main();
})();
