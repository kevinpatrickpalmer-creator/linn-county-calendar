/**
 * Big Ideas Board API -- Linn County Community Calendar
 *
 * This is the live backend for docs/big-ideas.html. It doesn't run on
 * GitHub Pages (that's static) -- it runs as a Google Apps Script Web
 * App bound to a Google Sheet, the same "Sheets as a free database"
 * pattern already used for email alert sign-ups (see
 * data/... README references to the alerts Google Form/Sheet). This
 * file is the source of truth for that script; Apps Script has no git
 * deploy, so setup is: create a Sheet, paste this file's contents into
 * its Apps Script editor, deploy as a Web App, and put the resulting
 * URL into docs/config.json as "big_ideas_api_url". See
 * apps-script/README.md for the exact steps.
 *
 * Two sheets, auto-created on first run:
 *   Ideas: id, title, description, name, town, submitted, upvotes,
 *          downvotes, example, status
 *   Votes: idea_id, voter_id, vote, updated
 *
 * Moderation: every real submission lands with status "pending" and
 * is invisible on the public page until someone changes that cell to
 * "approved" directly in the sheet -- same manual-review principle as
 * every other board on the site (Trading Post, Jobs, Lost & Found),
 * just done in a spreadsheet cell instead of a GitHub file. Voting
 * itself isn't gated -- it's just numbers, nothing to moderate.
 *
 * Voting is anonymous but not spoofable-by-accident: the page hands
 * every visitor a random ID (localStorage), sent with each vote, so
 * clicking an arrow twice toggles it off rather than double-counting.
 * It's not cryptographically enforced (clearing localStorage resets
 * it) -- fine for gauging interest on a small community board, not
 * meant to survive a determined attempt to stuff the ballot.
 */

const IDEAS_SHEET = "Ideas";
const VOTES_SHEET = "Votes";
const ADMIN_EMAIL = "kevinpatrickpalmer@gmail.com";

function getSheet(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(name);
  if (sheet) return sheet;

  sheet = ss.insertSheet(name);
  if (name === IDEAS_SHEET) {
    sheet.appendRow(["id", "title", "description", "name", "town", "submitted", "upvotes", "downvotes", "example", "status"]);
    // Seeded so the board never looks empty before anyone's posted for
    // real -- same reasoning as the pinned example on Jobs Bulletin and
    // Trading Post. Always shown regardless of status since example=true.
    sheet.appendRow([
      "example-1",
      "A community garden near the park (example)",
      "This is a sample idea to show the format — real ideas work just like this. A shared garden plot where families could grow their own vegetables, with a small tool shed the town maintains.",
      "", "",
      new Date().toISOString(),
      0, 0, true, "approved",
    ]);
  } else if (name === VOTES_SHEET) {
    sheet.appendRow(["idea_id", "voter_id", "vote", "updated"]);
  }
  return sheet;
}

function doGet(e) {
  const action = (e.parameter.action || "list");
  if (action === "list") {
    return jsonResponse(listIdeas(e.parameter.voterId || ""));
  }
  return jsonResponse({ error: "Unknown action" });
}

function doPost(e) {
  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonResponse({ success: false, error: "Invalid request" });
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    if (body.action === "submit") return jsonResponse(submitIdea(body));
    if (body.action === "vote") return jsonResponse(castVote(body));
    return jsonResponse({ success: false, error: "Unknown action" });
  } finally {
    lock.releaseLock();
  }
}

function sheetToObjects(sheet) {
  const values = sheet.getDataRange().getValues();
  const header = values[0];
  const idx = {};
  header.forEach((h, i) => { idx[h] = i; });
  const rows = values.slice(1).filter((r) => r[idx.id] || r[idx.idea_id]);
  return { idx, rows };
}

function listIdeas(voterId) {
  const { idx, rows } = sheetToObjects(getSheet(IDEAS_SHEET));

  let myVotes = {};
  if (voterId) {
    const votes = sheetToObjects(getSheet(VOTES_SHEET));
    for (const r of votes.rows) {
      if (r[votes.idx.voter_id] === voterId) {
        myVotes[r[votes.idx.idea_id]] = Number(r[votes.idx.vote]);
      }
    }
  }

  const ideas = rows
    .filter((r) => r[idx.example] === true || String(r[idx.status]).toLowerCase() === "approved")
    .map((r) => ({
      id: r[idx.id],
      title: r[idx.title],
      description: r[idx.description],
      name: r[idx.name] || "",
      town: r[idx.town] || "",
      submitted: r[idx.submitted],
      upvotes: Number(r[idx.upvotes] || 0),
      downvotes: Number(r[idx.downvotes] || 0),
      example: r[idx.example] === true,
      myVote: myVotes[r[idx.id]] || 0,
    }));

  ideas.sort((a, b) => {
    if (a.example !== b.example) return a.example ? -1 : 1;
    const scoreDiff = (b.upvotes - b.downvotes) - (a.upvotes - a.downvotes);
    if (scoreDiff !== 0) return scoreDiff;
    return new Date(b.submitted) - new Date(a.submitted);
  });

  return { ideas };
}

function submitIdea(body) {
  const honeypot = (body.botcheck || "").toString().trim();
  if (honeypot) return { success: true }; // silently drop bots, pretend success

  const title = (body.title || "").toString().trim().slice(0, 120);
  const description = (body.description || "").toString().trim().slice(0, 1000);
  const name = (body.name || "").toString().trim().slice(0, 100);
  const town = (body.town || "").toString().trim().slice(0, 60);

  if (!title || !description) {
    return { success: false, error: "Title and description are required." };
  }

  const sheet = getSheet(IDEAS_SHEET);
  const id = Utilities.getUuid();
  sheet.appendRow([id, title, description, name, town, new Date().toISOString(), 0, 0, false, "pending"]);

  try {
    MailApp.sendEmail(
      ADMIN_EMAIL,
      "New Big Idea pending review: " + title,
      "A new idea was submitted to the Big Ideas board.\n\n" +
        "Title: " + title + "\n" +
        "Description: " + description + "\n" +
        "From: " + (name || "(no name given)") + (town ? ", " + town : "") + "\n\n" +
        "It won't show on the site until you change its \"status\" cell from " +
        "\"pending\" to \"approved\" in the sheet:\n" +
        SpreadsheetApp.getActiveSpreadsheet().getUrl()
    );
  } catch (err) {
    // Sheet write already succeeded; a failed notification email isn't
    // worth failing the whole submission over.
  }

  return { success: true, id };
}

function castVote(body) {
  const ideaId = (body.ideaId || "").toString();
  const voterId = (body.voterId || "").toString();
  const direction = body.vote === 1 ? 1 : (body.vote === -1 ? -1 : 0);

  if (!ideaId || !voterId || !direction) {
    return { success: false, error: "Missing vote info." };
  }

  const votesSheet = getSheet(VOTES_SHEET);
  const { idx: vIdx, rows: vRows } = sheetToObjects(votesSheet);

  let existingRowNum = -1;
  let existingVote = 0;
  for (let i = 0; i < vRows.length; i++) {
    if (vRows[i][vIdx.idea_id] === ideaId && vRows[i][vIdx.voter_id] === voterId) {
      existingRowNum = i + 2; // +1 for header, +1 for 1-indexing
      existingVote = Number(vRows[i][vIdx.vote]);
      break;
    }
  }

  // Clicking the same direction again un-votes (toggle); the opposite
  // direction switches the vote.
  const newVote = existingVote === direction ? 0 : direction;

  if (existingRowNum === -1) {
    votesSheet.appendRow([ideaId, voterId, newVote, new Date().toISOString()]);
  } else {
    votesSheet.getRange(existingRowNum, 3).setValue(newVote);
    votesSheet.getRange(existingRowNum, 4).setValue(new Date().toISOString());
  }

  // Recompute this idea's tallies from the Votes sheet (source of
  // truth) rather than incrementing counters, so they can never drift.
  const { idx: vIdx2, rows: vRows2 } = sheetToObjects(votesSheet);
  let up = 0, down = 0;
  for (const r of vRows2) {
    if (r[vIdx2.idea_id] !== ideaId) continue;
    const v = Number(r[vIdx2.vote]);
    if (v === 1) up++;
    if (v === -1) down++;
  }

  const ideasSheet = getSheet(IDEAS_SHEET);
  const { idx: iIdx, rows: iRows } = sheetToObjects(ideasSheet);
  for (let i = 0; i < iRows.length; i++) {
    if (iRows[i][iIdx.id] === ideaId) {
      const rowNum = i + 2;
      ideasSheet.getRange(rowNum, iIdx.upvotes + 1).setValue(up);
      ideasSheet.getRange(rowNum, iIdx.downvotes + 1).setValue(down);
      break;
    }
  }

  return { success: true, upvotes: up, downvotes: down, myVote: newVote };
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
