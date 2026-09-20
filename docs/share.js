// Shared "share this" row (Facebook/WhatsApp/Instagram/Email/Copy Link).
// Styling already lives in theme.css (.share-label/.share-row/.share-btn.*),
// so this only builds the markup and wires the five buttons -- pulled out
// of docs/subscribe.html, which had its own hand-written copy of all this,
// so every page can have one without copy-pasting five SVGs into each file.
//
// Two ways to use it:
//   1. Auto-mount, for a page sharing itself: just include the script,
//      no other markup needed.
//        <script src="share.js" data-text="..." data-subject="..."></script>
//      Mounts right before .site-credit, which every page has at the
//      bottom. url/text/subject default to the current page's own
//      location/title if data-text/data-subject aren't set.
//   2. Manual, for a submission confirmation sharing the *board* it just
//      posted to rather than the submit form's own page (see e.g.
//      docs/submit-job.html): add data-manual to skip auto-mount, then
//      call window.renderShareRow(container, {url, text, subject}) by
//      hand once the confirmation shows.
(function () {
  const ICONS = {
    facebook: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M22 12.06C22 6.53 17.52 2 12 2S2 6.53 2 12.06c0 5 3.66 9.13 8.44 9.94v-7.03H7.9v-2.91h2.54V9.85c0-2.51 1.49-3.89 3.77-3.89 1.09 0 2.24.2 2.24.2v2.46h-1.26c-1.24 0-1.63.77-1.63 1.56v1.88h2.78l-.44 2.91h-2.34V22c4.78-.81 8.44-4.94 8.44-9.94Z"/></svg>',
    whatsapp: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12.02 2C6.5 2 2 6.48 2 11.98c0 1.98.58 3.83 1.58 5.39L2 22l4.79-1.53a10 10 0 0 0 5.23 1.47h.01c5.52 0 10-4.48 10-9.98A9.94 9.94 0 0 0 12.02 2Zm5.45 12.38c-.29.68-1.46 1.31-1.97 1.39-.5.08-1.14.11-1.84-.11-.43-.13-.97-.31-1.67-.61-2.94-1.26-4.85-4.2-5-4.4-.14-.19-1.19-1.58-1.19-3.02 0-1.43.75-2.14 1.02-2.43.27-.3.58-.37.78-.37h.56c.18.01.42-.06.66.51.24.59.83 2.02.9 2.17.07.14.12.31.02.51-.24.49-.44.6-.29.85.15.19.73 1.23 1.61 2 1.11.99 2.04 1.29 2.33 1.44.29.15.46.13.63-.07.17-.2.73-.85.93-1.14.2-.3.39-.25.66-.15.27.1 1.71.8 2 .95.29.15.48.22.55.34.08.12.08.71-.16 1.39Z"/></svg>',
    instagram: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2c-2.72 0-3.06.01-4.12.06-1.06.05-1.79.22-2.43.47a4.9 4.9 0 0 0-1.77 1.15A4.9 4.9 0 0 0 2.53 5.45c-.25.64-.42 1.37-.47 2.43C2 8.94 2 9.28 2 12s.01 3.06.06 4.12c.05 1.06.22 1.79.47 2.43a4.9 4.9 0 0 0 1.15 1.77 4.9 4.9 0 0 0 1.77 1.15c.64.25 1.37.42 2.43.47C8.94 22 9.28 22 12 22s3.06-.01 4.12-.06c1.06-.05 1.79-.22 2.43-.47a4.9 4.9 0 0 0 1.77-1.15 4.9 4.9 0 0 0 1.15-1.77c.25-.64.42-1.37.47-2.43.05-1.06.06-1.4.06-4.12s-.01-3.06-.06-4.12c-.05-1.06-.22-1.79-.47-2.43a4.9 4.9 0 0 0-1.15-1.77A4.9 4.9 0 0 0 18.55 2.53c-.64-.25-1.37-.42-2.43-.47C15.06 2.01 14.72 2 12 2Zm0 1.8c2.67 0 2.99.01 4.04.06.98.04 1.5.21 1.86.34.47.18.8.4 1.15.75.35.35.57.68.75 1.15.13.36.3.88.34 1.86.05 1.05.06 1.37.06 4.04s-.01 2.99-.06 4.04c-.04.98-.21 1.5-.34 1.86-.18.47-.4.8-.75 1.15-.35.35-.68.57-1.15.75-.36.13-.88.3-1.86.34-1.05.05-1.37.06-4.04.06s-2.99-.01-4.04-.06c-.98-.04-1.5-.21-1.86-.34a3.1 3.1 0 0 1-1.15-.75 3.1 3.1 0 0 1-.75-1.15c-.13-.36-.3-.88-.34-1.86C3.81 14.99 3.8 14.67 3.8 12s.01-2.99.06-4.04c.04-.98.21-1.5.34-1.86.18-.47.4-.8.75-1.15.35-.35.68-.57 1.15-.75.36-.13.88-.3 1.86-.34C9.01 3.81 9.33 3.8 12 3.8Zm0 3.05a5.15 5.15 0 1 0 0 10.3 5.15 5.15 0 0 0 0-10.3Zm0 8.5a3.35 3.35 0 1 1 0-6.7 3.35 3.35 0 0 1 0 6.7Zm5.35-8.7a1.2 1.2 0 1 1-2.4 0 1.2 1.2 0 0 1 2.4 0Z"/></svg>',
    email: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3 5.5A1.5 1.5 0 0 1 4.5 4h15A1.5 1.5 0 0 1 21 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5v-13Zm2.1.5 6.9 5.2L18.9 6H5.1Zm13.9 1.4-6.55 4.94a1 1 0 0 1-1.2 0L5.7 7.4V18h13.3V7.4Z"/></svg>',
    copylink: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M10.6 13.4a1 1 0 0 1 0-1.4l3-3a3 3 0 1 1 4.24 4.24l-1.4 1.4a1 1 0 1 1-1.42-1.42l1.4-1.4a1 1 0 1 0-1.4-1.4l-3 3a1 1 0 0 1-1.42 0Zm2.8-2.8a1 1 0 0 1 0 1.4l-3 3a3 3 0 1 1-4.24-4.24l1.4-1.4a1 1 0 0 1 1.42 1.42l-1.4 1.4a1 1 0 1 0 1.4 1.4l3-3a1 1 0 0 1 1.42 0Z"/></svg>',
  };

  window.renderShareRow = function (container, opts) {
    opts = opts || {};
    const url = opts.url || location.href;
    const text = opts.text || document.title;
    const subject = opts.subject || document.title;
    const label = opts.label || "Know someone who'd want this? Share it:";

    container.innerHTML =
      `<p class="share-label">${label}</p>` +
      `<div class="share-row">` +
      `<a class="share-btn facebook" href="#" target="_blank" rel="noopener" aria-label="Share on Facebook">${ICONS.facebook}Facebook</a>` +
      `<a class="share-btn whatsapp" href="#" target="_blank" rel="noopener" aria-label="Share on WhatsApp">${ICONS.whatsapp}WhatsApp</a>` +
      `<button class="share-btn instagram" type="button" aria-label="Copy link to share on Instagram">${ICONS.instagram}<span class="share-copy-label">Instagram</span></button>` +
      `<a class="share-btn email" href="#" aria-label="Share by email">${ICONS.email}Email</a>` +
      `<button class="share-btn copylink" type="button" aria-label="Copy link">${ICONS.copylink}<span class="share-copy-label">Copy Link</span></button>` +
      `</div>` +
      `<p class="hint">Instagram doesn't support direct share links, tap its button above to copy your link, then paste it into your bio, a story, or a DM.</p>`;

    container.querySelector(".share-btn.facebook").href =
      `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`;
    container.querySelector(".share-btn.whatsapp").href =
      `https://wa.me/?text=${encodeURIComponent(`${text} ${url}`)}`;
    container.querySelector(".share-btn.email").href =
      `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(`${text}\n\n${url}`)}`;

    function wireCopyButton(btn) {
      const labelEl = btn.querySelector(".share-copy-label");
      const defaultLabel = labelEl.textContent;
      btn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(url);
          labelEl.textContent = "Copied!";
          btn.classList.add("copied");
        } catch (err) {
          // Clipboard API needs a secure context/permission -- fall back
          // to just showing the link so the visitor can copy it by hand.
          labelEl.textContent = url;
        }
        setTimeout(() => {
          labelEl.textContent = defaultLabel;
          btn.classList.remove("copied");
        }, 2500);
      });
    }
    wireCopyButton(container.querySelector(".share-btn.instagram"));
    wireCopyButton(container.querySelector(".share-btn.copylink"));
  };

  // Auto-mount unless this script tag opts out (data-manual) -- captured
  // synchronously here since document.currentScript is only reliable
  // during the script's own initial run, not later inside a callback.
  const thisScript = document.currentScript;
  if (thisScript && !thisScript.hasAttribute("data-manual")) {
    document.addEventListener("DOMContentLoaded", () => {
      const anchor = document.querySelector(".site-credit");
      if (!anchor) return;
      const section = document.createElement("div");
      section.className = "share-section";
      anchor.parentNode.insertBefore(section, anchor);
      renderShareRow(section, {
        text: thisScript.getAttribute("data-text") || undefined,
        subject: thisScript.getAttribute("data-subject") || undefined,
      });
    });
  }
})();
