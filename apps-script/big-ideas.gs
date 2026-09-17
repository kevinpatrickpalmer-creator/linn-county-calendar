/**
 * Site backend -- Linn County Community Calendar
 *
 * Started as just the live backend for docs/big-ideas.html (voting
 * needs somewhere live; a static GitHub Pages site can't do that on
 * its own). Now also handles submissions for every other board on the
 * site (events, business directory, trading post, jobs, lost & found):
 * each submit page POSTs here instead of Web3Forms, a notification
 * email goes out, and replying "approved" commits the right JSON file
 * straight to the GitHub repo -- no more manually clicking through to
 * GitHub's "create file" page. Same Sheets-as-a-free-database idea
 * throughout. This file is the source of truth; Apps Script has no git
 * deploy, so setup is manual -- see apps-script/README.md.
 *
 * Sheets, auto-created on first run:
 *   Ideas: id, title, description, name, town, submitted, upvotes,
 *          downvotes, example, status
 *   Votes: idea_id, voter_id, vote, updated
 *   Pending: id, board, data_json, submitted, status
 *     (one row per event/business/trading-post/job/lost-found
 *     submission; data_json holds that board's own fields, since each
 *     board has a different shape -- see BOARD_CONFIG below)
 *
 * Moderation: every real submission lands with status "pending" and
 * only becomes real (visible on the site, or committed to GitHub) once
 * that changes to "approved" -- same manual-review principle every
 * board on this site has always had, just automated now. Two ways to
 * approve: reply "approved" or "rejected" to the notification email
 * (checked every few minutes, see checkForReplies()), or edit the
 * "status" cell in the sheet by hand. Voting on Big Ideas isn't
 * gated -- it's just numbers, nothing to moderate.
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
const PENDING_SHEET = "Pending";
const ADMIN_EMAIL = "kevinpatrickpalmer@gmail.com";
const GITHUB_REPO = "kevinpatrickpalmer-creator/linn-county-calendar";
const GITHUB_BRANCH = "main";
const SITE_STATE = "MO";

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
  } else if (name === PENDING_SHEET) {
    sheet.appendRow(["id", "board", "data_json", "submitted", "status"]);
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
    if (body.action === "submitBoard") return jsonResponse(submitBoardEntry(body));
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
    // The #<refCode> tag rides along in the subject through Gmail's
    // "Re:" reply -- checkForReplies() below reads it back out to know
    // which row a reply belongs to, without needing to track thread ids.
    const refCode = id.slice(-8);
    MailApp.sendEmail(
      ADMIN_EMAIL,
      "New Big Idea pending review: " + title + " #" + refCode,
      "A new idea was submitted to the Big Ideas board.\n\n" +
        "Title: " + title + "\n" +
        "Description: " + description + "\n" +
        "From: " + (name || "(no name given)") + (town ? ", " + town : "") + "\n\n" +
        "Reply to this email with just the word \"approved\" or \"rejected\" " +
        "and it'll update the board automatically within a few minutes -- " +
        "or open the sheet directly and change the \"status\" cell by hand:\n" +
        SpreadsheetApp.getActiveSpreadsheet().getUrl()
    );
  } catch (err) {
    // Sheet write already succeeded; a failed notification email isn't
    // worth failing the whole submission over.
  }

  return { success: true, id };
}

// ---------------------------------------------------------------------
// Board submissions (events, business directory, trading post, jobs,
// lost & found) -- each submit-*.html page POSTs {action:"submitBoard",
// board, fields, submitterName, botcheck} here instead of Web3Forms.
// ---------------------------------------------------------------------

function slugify(text) {
  return (text || "").toString().toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

// Mirrors formatTime12h() in docs/submit.html / the old admin.html --
// same "14:30" -> "2:30 pm" conversion, just done here now since this
// is what actually writes the published JSON's time fields.
function formatTime12h(value) {
  if (!value) return "";
  const parts = value.split(":");
  const h = Number(parts[0]);
  const m = Number(parts[1]);
  if (isNaN(h) || isNaN(m)) return "";
  const period = h >= 12 ? "pm" : "am";
  const hour12 = ((h + 11) % 12) + 1;
  return hour12 + ":" + String(m).padStart(2, "0") + " " + period;
}

const BOARD_LABELS = {
  event: "Event",
  business: "Directory listing",
  "trading-post": "Trading Post listing",
  job: "Jobs Bulletin post",
  "lost-found": "Lost & Found post",
};

// Mirrors each board's old admin-*.html "build the JSON, then open a
// GitHub create-file link" logic exactly -- same field sets, same
// filename conventions, same required fields as
// build_*.py/data/*/README.md already document. publishBoardEntry()
// below is what actually calls these once a submission is approved.
const BOARD_CONFIG = {
  event: {
    dir: "data/manual_events",
    requiredFields: ["name", "date"],
    buildFilename: function (f) {
      return f.date + "-" + (slugify(f.name) || "event") + ".json";
    },
    buildContent: function (f) {
      const location = f.venue && f.town
        ? f.venue + " | " + f.town + ", " + SITE_STATE
        : (f.town ? f.town + ", " + SITE_STATE : "");
      // Contact/website/online-link aren't fields of their own in the
      // published schema -- folded into the description (clearly
      // labeled) so they're still visible on the calendar listing
      // rather than silently dropped.
      let description = f.description || "";
      const extraLines = [];
      if (f.contact) extraLines.push("Contact: " + f.contact);
      if (f.website) extraLines.push("Website: " + f.website);
      if (f.online_link) extraLines.push("Online: " + f.online_link);
      if (extraLines.length) description = (description ? description + "\n\n" : "") + extraLines.join("\n");
      const obj = {
        name: f.name,
        date: f.date,
        time: formatTime12h(f.time),
        location: location,
        description: description,
      };
      const endTime = formatTime12h(f.end_time);
      if (endTime) obj.end_time = endTime;
      if (f.event_type) obj.event_type = f.event_type;
      if (f.recurrence && f.recurrence !== "none" && f.repeat_until) {
        obj.recurrence = f.recurrence;
        obj.repeat_until = f.repeat_until;
      }
      return obj;
    },
  },
  business: {
    dir: "data/businesses",
    requiredFields: ["name", "town"],
    buildFilename: function (f) {
      return slugify(f.town) + "-" + (slugify(f.name) || "listing") + ".json";
    },
    buildContent: function (f) {
      const obj = { name: f.name, town: f.town };
      ["category", "address", "phone", "website", "email", "hours", "description"].forEach(function (k) {
        if (f[k]) obj[k] = f[k];
      });
      return obj;
    },
  },
  "trading-post": {
    dir: "data/trading-post",
    requiredFields: ["name", "town"],
    buildFilename: function (f) {
      return slugify(f.town) + "-" + (slugify(f.name) || "listing") + ".json";
    },
    buildContent: function (f) {
      const obj = { name: f.name, town: f.town };
      ["category", "description", "availability", "phone", "email", "website"].forEach(function (k) {
        if (f[k]) obj[k] = f[k];
      });
      return obj;
    },
  },
  job: {
    dir: "data/jobs",
    requiredFields: ["type", "name", "town", "description"],
    buildFilename: function (f, today) {
      return slugify(f.town) + "-" + (slugify(f.name) || "post") + "-" + today + ".json";
    },
    buildContent: function (f, today) {
      const obj = { type: f.type, name: f.name, town: f.town, posted: today };
      ["category", "description", "phone", "email"].forEach(function (k) {
        if (f[k]) obj[k] = f[k];
      });
      return obj;
    },
  },
  "lost-found": {
    dir: "data/lost-found",
    requiredFields: ["type", "category", "name", "town", "date", "description"],
    buildFilename: function (f, today) {
      return slugify(f.town) + "-" + (slugify(f.name) || "post") + "-" + today + ".json";
    },
    buildContent: function (f, today) {
      const obj = { type: f.type, category: f.category, name: f.name, town: f.town };
      ["date", "description", "contact_name", "phone", "email", "photo"].forEach(function (k) {
        if (f[k]) obj[k] = f[k];
      });
      obj.posted = today;
      return obj;
    },
  },
};

function submitBoardEntry(body) {
  const honeypot = (body.botcheck || "").toString().trim();
  if (honeypot) return { success: true }; // silently drop bots, pretend success

  const board = (body.board || "").toString();
  const cfg = BOARD_CONFIG[board];
  if (!cfg) return { success: false, error: "Unknown board." };

  const rawFields = body.fields || {};
  const fields = {};
  for (const key in rawFields) {
    const v = rawFields[key];
    fields[key] = typeof v === "string" ? v.trim().slice(0, 2000) : v;
  }

  for (const i in cfg.requiredFields) {
    const req = cfg.requiredFields[i];
    if (!fields[req]) return { success: false, error: "Missing required field: " + req };
  }
  if (board === "job" && ["needed", "offering"].indexOf(fields.type) === -1) {
    return { success: false, error: "Invalid type." };
  }
  if (board === "lost-found" && ["lost", "found"].indexOf(fields.type) === -1) {
    return { success: false, error: "Invalid type." };
  }

  const id = Utilities.getUuid();
  const submitterName = (body.submitterName || "").toString().trim();

  // Lost & Found photos: uploaded to GitHub right away rather than
  // held in the sheet, which has a per-cell size limit far smaller
  // than a typical photo. It sits unreferenced by any public JSON
  // file (so it's invisible on the site) until the post is approved;
  // if rejected, it's deleted again.
  if (board === "lost-found" && body.photoBase64 && body.photoExt) {
    try {
      const ext = body.photoExt.toString().replace(/[^a-z0-9]/gi, "").toLowerCase() || "jpg";
      const photoPath = "docs/lost-found-photos/pending-" + id + "." + ext;
      githubPutFile(photoPath, body.photoBase64, "Add Lost & Found photo (pending review)", true);
      fields.photo = photoPath.replace(/^docs\//, "");
    } catch (err) {
      // Photo upload failing shouldn't block the text submission --
      // it can be added by hand later if it matters.
    }
  }

  const pendingSheet = getSheet(PENDING_SHEET);
  pendingSheet.appendRow([id, board, JSON.stringify(fields), new Date().toISOString(), "pending"]);

  try {
    const refCode = id.slice(-8);
    const boardLabel = BOARD_LABELS[board] || board;
    const summaryLines = Object.keys(fields)
      .filter(function (k) { return k !== "photo"; })
      .map(function (k) { return k + ": " + fields[k]; })
      .join("\n");
    MailApp.sendEmail(
      ADMIN_EMAIL,
      "New " + boardLabel + " submission pending review #" + refCode,
      "A new " + boardLabel.toLowerCase() + " submission came in" + (submitterName ? " from " + submitterName : "") + ".\n\n" +
        summaryLines + "\n\n" +
        "Reply to this email with just the word \"approved\" or \"rejected\" and it'll be handled " +
        "automatically within a few minutes -- approved publishes it to the site, rejected discards it. " +
        "No other action needed, though you can also review it directly in the \"Pending\" sheet tab:\n" +
        SpreadsheetApp.getActiveSpreadsheet().getUrl()
    );
  } catch (err) {
    // Row already saved; a failed notification email isn't worth failing over.
  }

  return { success: true, id };
}

function publishBoardEntry(board, fields, today) {
  const cfg = BOARD_CONFIG[board];
  const filename = cfg.buildFilename(fields, today);
  const content = cfg.buildContent(fields, today);
  const path = cfg.dir + "/" + filename;
  githubPutFile(path, JSON.stringify(content, null, 2) + "\n", "Approve " + board + " submission via email reply", false);
}

// ---------------------------------------------------------------------
// GitHub API -- committing files directly via the Contents API, using
// a personal access token stored in Script Properties (Project
// Settings in the Apps Script editor), never in this file. Scope it
// narrowly: a fine-grained token limited to just this one repo, with
// "Contents: Read and write" and nothing else. See apps-script/README.md.
// ---------------------------------------------------------------------

function githubToken() {
  const token = PropertiesService.getScriptProperties().getProperty("GITHUB_TOKEN");
  if (!token) throw new Error("GITHUB_TOKEN is not set in Script Properties.");
  return token;
}

function githubPutFile(path, content, message, contentIsBase64) {
  const token = githubToken();
  const url = "https://api.github.com/repos/" + GITHUB_REPO + "/contents/" + path;
  const contentBase64 = contentIsBase64 ? content : Utilities.base64Encode(content, Utilities.Charset.UTF_8);
  const payload = { message: message, content: contentBase64, branch: GITHUB_BRANCH };
  const res = UrlFetchApp.fetch(url, {
    method: "put",
    contentType: "application/json",
    headers: { Authorization: "token " + token, Accept: "application/vnd.github+json" },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });
  const code = res.getResponseCode();
  if (code !== 200 && code !== 201) {
    throw new Error("GitHub API error " + code + ": " + res.getContentText());
  }
  return JSON.parse(res.getContentText());
}

function githubDeleteFile(path, message) {
  const token = githubToken();
  const url = "https://api.github.com/repos/" + GITHUB_REPO + "/contents/" + path;
  const getRes = UrlFetchApp.fetch(url + "?ref=" + GITHUB_BRANCH, {
    headers: { Authorization: "token " + token, Accept: "application/vnd.github+json" },
    muteHttpExceptions: true,
  });
  if (getRes.getResponseCode() !== 200) return; // already gone -- nothing to do
  const sha = JSON.parse(getRes.getContentText()).sha;
  UrlFetchApp.fetch(url, {
    method: "delete",
    contentType: "application/json",
    headers: { Authorization: "token " + token, Accept: "application/vnd.github+json" },
    payload: JSON.stringify({ message: message, sha: sha, branch: GITHUB_BRANCH }),
    muteHttpExceptions: true,
  });
}

/**
 * Reply-to-approve/reject: run installReplyTrigger() once (from the
 * Apps Script editor's function dropdown, or see apps-script/README.md)
 * to schedule this to run every 5 minutes. It looks for unread replies
 * to any "pending review" notification -- Big Ideas or a board
 * submission -- reads the #<refCode> back out of the subject line
 * (Gmail keeps it through "Re:"), and applies the decision if the
 * reply plainly says "approved" or "rejected". Anything ambiguous
 * (both words, or neither) is left unread for a person to sort out by
 * hand instead of guessing wrong.
 */
function checkForReplies() {
  const threads = GmailApp.search('in:inbox is:unread (subject:"Big Idea pending review" OR subject:"submission pending review")', 0, 20);
  for (const thread of threads) {
    const messages = thread.getMessages();
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage.isUnread()) continue;

    const subject = thread.getFirstMessageSubject();
    const refMatch = subject.match(/#([A-Za-z0-9]{8})/);
    if (!refMatch) continue; // not a reply we know how to match to a row
    const refCode = refMatch[1].toLowerCase();

    // Gmail's own "On <date> ... wrote:" line marks where the quoted
    // original starts -- only the text above it is this reply's own
    // words. If that split ever fails to match, scanning the whole
    // body is still safe: every notification email's own instructional
    // line always says "approved" AND "rejected" together, which the
    // both-words-present check below treats as ambiguous, not a match.
    const body = lastMessage.getPlainBody();
    const replyText = body.split(/\nOn .+wrote:\n/)[0].toLowerCase();
    const hasApproved = /\bapproved\b/.test(replyText);
    const hasRejected = /\brejected\b/.test(replyText);

    let newStatus = null;
    if (hasApproved && !hasRejected) newStatus = "approved";
    else if (hasRejected && !hasApproved) newStatus = "rejected";
    if (!newStatus) continue;

    let handled = false;
    if (subject.indexOf("Big Idea pending review") !== -1) {
      handled = applyIdeaDecision(refCode, newStatus);
    } else if (subject.indexOf("submission pending review") !== -1) {
      handled = applyBoardDecision(refCode, newStatus);
    }
    if (handled) lastMessage.markRead();
  }
}

function applyIdeaDecision(refCode, newStatus) {
  const sheet = getSheet(IDEAS_SHEET);
  const { idx, rows } = sheetToObjects(sheet);
  for (let i = 0; i < rows.length; i++) {
    if (String(rows[i][idx.id]).slice(-8).toLowerCase() === refCode) {
      sheet.getRange(i + 2, idx.status + 1).setValue(newStatus);
      return true;
    }
  }
  return false;
}

function applyBoardDecision(refCode, newStatus) {
  const sheet = getSheet(PENDING_SHEET);
  const { idx, rows } = sheetToObjects(sheet);
  for (let i = 0; i < rows.length; i++) {
    const id = String(rows[i][idx.id]);
    if (id.slice(-8).toLowerCase() !== refCode) continue;

    const rowNum = i + 2;
    const board = rows[i][idx.board];
    const fields = JSON.parse(rows[i][idx.data_json]);

    if (newStatus === "approved") {
      try {
        const today = new Date().toISOString().slice(0, 10);
        publishBoardEntry(board, fields, today);
        sheet.getRange(rowNum, idx.status + 1).setValue("approved");
      } catch (err) {
        // Don't silently lose the submission -- leave a visible trail
        // for a person to follow up on instead of just marking it done.
        sheet.getRange(rowNum, idx.status + 1).setValue("error: " + err.message);
      }
    } else {
      // fields.photo is stored relative to docs/ (matching the "photo"
      // field's own published form), but the file actually lives at
      // docs/<that path> in the repo -- same prefix submitBoardEntry()
      // uploaded it to, needed here too or the delete silently 404s.
      if (fields.photo) {
        try { githubDeleteFile("docs/" + fields.photo, "Remove photo for rejected Lost & Found post"); } catch (err) {}
      }
      sheet.getRange(rowNum, idx.status + 1).setValue("rejected");
    }
    return true;
  }
  return false;
}

function installReplyTrigger() {
  for (const trigger of ScriptApp.getProjectTriggers()) {
    if (trigger.getHandlerFunction() === "checkForReplies") {
      ScriptApp.deleteTrigger(trigger);
    }
  }
  ScriptApp.newTrigger("checkForReplies").timeBased().everyMinutes(5).create();
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
