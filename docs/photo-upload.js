// Shared "up to 3 photos" handling for a <input type="file" multiple>
// field -- used by every submit-*.html page that accepts photos
// (Lost & Found, Business, Trading Post, Jobs, Clubs & Classes).
// Two pieces: trimming the selection down to 3 with visible feedback
// the moment someone picks more, and reading whatever's left into the
// base64 form the Apps Script backend expects.
(function () {
  // A <input type=file multiple>'s FileList can't be edited directly,
  // so trimming to the first 3 means building a fresh FileList (via
  // DataTransfer) and reassigning it back onto the input -- that keeps
  // what's actually selected in sync with what the hint says, rather
  // than just silently dropping the extras at submit time.
  window.wirePhotoCap = function (inputId, hintId) {
    const input = document.getElementById(inputId);
    const hint = document.getElementById(hintId);
    const defaultHint = hint.textContent;
    input.addEventListener("change", () => {
      if (input.files.length > 3) {
        const trimmed = new DataTransfer();
        Array.from(input.files).slice(0, 3).forEach((f) => trimmed.items.add(f));
        input.files = trimmed.files;
        hint.textContent = "Only the first 3 photos are used, the rest were dropped.";
        hint.classList.add("err");
      } else {
        hint.textContent = defaultHint;
        hint.classList.remove("err");
      }
    });
  };

  // Returns a Promise resolving to an array of {base64, ext}, one per
  // selected photo (already capped at 3 by wirePhotoCap above, but
  // sliced again here as a second guarantee). A photo that fails to
  // read client-side is just skipped rather than blocking the rest of
  // the submission over it.
  window.readPhotos = async function (inputId) {
    const files = Array.from(document.getElementById(inputId).files).slice(0, 3);
    const photos = [];
    for (const file of files) {
      try {
        const dataUrl = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.onerror = reject;
          reader.readAsDataURL(file);
        });
        const extMatch = file.name.match(/\.([a-zA-Z0-9]+)$/);
        photos.push({ base64: dataUrl.split(",")[1] || "", ext: extMatch ? extMatch[1] : "jpg" });
      } catch (err) {
        // Skip it -- see comment above.
      }
    }
    return photos;
  };
})();
