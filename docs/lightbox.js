// Shared click-to-enlarge photo viewer, used by every board page that
// shows photos (Lost & Found, Business Directory, Jobs Bulletin, Clubs &
// Classes, Trading Post). Two pieces: renderPhotoStrip() builds the
// thumbnail(s) on a card, and openLightbox() shows the full-size overlay.
// The overlay markup/styles are built once, lazily, on first open --
// most page visits never open one, so there's no point paying for it on
// every load.
(function () {
  let overlay, imgEl, counterEl, prevBtn, nextBtn;
  let currentPhotos = [];
  let currentIndex = 0;
  let restoreFocusTo = null;

  function ensureOverlay() {
    if (overlay) return;

    const style = document.createElement("style");
    style.textContent = `
      .lightbox-overlay {
        position: fixed; inset: 0; z-index: 2000;
        background: rgba(0, 0, 0, .9);
        display: flex; align-items: center; justify-content: center;
        padding: 2.5rem 1rem;
      }
      .lightbox-overlay[hidden] { display: none; }
      .lightbox-overlay img {
        max-width: 92vw; max-height: 82vh;
        object-fit: contain;
        border-radius: var(--radius-sm);
        display: block;
      }
      .lightbox-close {
        position: absolute; top: 1rem; right: 1.1rem;
        width: 2.5rem; height: 2.5rem;
        border-radius: 50%; border: none;
        background: rgba(255, 255, 255, .12); color: var(--ink);
        font-size: 1.5rem; line-height: 1; cursor: pointer;
      }
      .lightbox-close:hover { background: rgba(255, 255, 255, .22); }
      .lightbox-nav {
        position: absolute; top: 50%; transform: translateY(-50%);
        width: 2.75rem; height: 2.75rem;
        border-radius: 50%; border: none;
        background: rgba(255, 255, 255, .12); color: var(--ink);
        font-size: 1.6rem; line-height: 1; cursor: pointer;
      }
      .lightbox-nav:hover { background: rgba(255, 255, 255, .22); }
      .lightbox-nav.prev { left: 1rem; }
      .lightbox-nav.next { right: 1rem; }
      .lightbox-counter {
        position: absolute; bottom: 1.1rem; left: 50%; transform: translateX(-50%);
        color: var(--ink-soft); font-size: .85rem; font-weight: 600;
      }
      .photo-strip { display: flex; gap: .35rem; margin-bottom: .2rem; }
      .photo-thumb {
        flex: 1; min-width: 0;
        aspect-ratio: 1 / 1; object-fit: cover;
        border-radius: var(--radius-sm);
        background: var(--surface-border);
        display: block; cursor: zoom-in;
      }
    `;
    document.head.appendChild(style);

    overlay = document.createElement("div");
    overlay.className = "lightbox-overlay";
    overlay.hidden = true;
    overlay.innerHTML = `
      <button type="button" class="lightbox-close" aria-label="Close">&times;</button>
      <button type="button" class="lightbox-nav prev" aria-label="Previous photo">&lsaquo;</button>
      <img alt="">
      <button type="button" class="lightbox-nav next" aria-label="Next photo">&rsaquo;</button>
      <p class="lightbox-counter"></p>
    `;
    document.body.appendChild(overlay);

    imgEl = overlay.querySelector("img");
    counterEl = overlay.querySelector(".lightbox-counter");
    prevBtn = overlay.querySelector(".lightbox-nav.prev");
    nextBtn = overlay.querySelector(".lightbox-nav.next");

    overlay.querySelector(".lightbox-close").addEventListener("click", closeLightbox);
    prevBtn.addEventListener("click", () => show(currentIndex - 1));
    nextBtn.addEventListener("click", () => show(currentIndex + 1));
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeLightbox();
    });
    document.addEventListener("keydown", (e) => {
      if (overlay.hidden) return;
      if (e.key === "Escape") closeLightbox();
      else if (e.key === "ArrowLeft") show(currentIndex - 1);
      else if (e.key === "ArrowRight") show(currentIndex + 1);
    });
  }

  function show(index) {
    currentIndex = (index + currentPhotos.length) % currentPhotos.length;
    imgEl.src = currentPhotos[currentIndex];
    const multi = currentPhotos.length > 1;
    prevBtn.hidden = !multi;
    nextBtn.hidden = !multi;
    counterEl.hidden = !multi;
    if (multi) counterEl.textContent = `${currentIndex + 1} / ${currentPhotos.length}`;
  }

  window.openLightbox = function (photos, startIndex) {
    if (!photos || !photos.length) return;
    ensureOverlay();
    currentPhotos = photos;
    restoreFocusTo = document.activeElement;
    overlay.hidden = false;
    show(startIndex || 0);
    overlay.querySelector(".lightbox-close").focus();
  };

  function closeLightbox() {
    overlay.hidden = true;
    imgEl.src = "";
    if (restoreFocusTo && restoreFocusTo.focus) restoreFocusTo.focus();
  }

  // Builds the thumbnail(s) for one card and appends them to it. Accepts
  // either an uploaded "photos" array (Lost & Found, and any board's own
  // submission form) or a single scraped "photo" string (Business
  // Directory only, from scrape_businesses.py) -- whichever the item has.
  // A single photo keeps the existing full-width look; more than one
  // shows as a row of equal-size thumbnails instead.
  window.renderPhotoStrip = function (card, item) {
    const photos = item.photos && item.photos.length ? item.photos : (item.photo ? [item.photo] : []);
    if (!photos.length) return;

    if (photos.length === 1) {
      const img = document.createElement("img");
      img.className = "biz-photo";
      img.src = photos[0];
      img.alt = "";
      img.loading = "lazy";
      img.style.cursor = "zoom-in";
      img.addEventListener("error", () => img.remove());
      img.addEventListener("click", () => openLightbox(photos, 0));
      card.appendChild(img);
      return;
    }

    const strip = document.createElement("div");
    strip.className = "photo-strip";
    photos.slice(0, 3).forEach((src, i) => {
      const img = document.createElement("img");
      img.className = "photo-thumb";
      img.src = src;
      img.alt = "";
      img.loading = "lazy";
      img.addEventListener("error", () => img.remove());
      img.addEventListener("click", () => openLightbox(photos, i));
      strip.appendChild(img);
    });
    card.appendChild(strip);
  };
})();
