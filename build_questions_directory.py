#!/usr/bin/env python3
"""
Builds docs/questions.json from every approved question in
data/questions/ (see data/questions/README.md for how a file lands
there), with each question's approved answers from data/answers/
nested under it as an "answers" array. This is the one board on the
site where two directories have to be joined at build time -- every
other board publishes standalone listings, but an Ask the Community
answer only makes sense attached to the question it answers.

Run:
    python build_questions_directory.py
"""
import glob
import json
import os
import sys
from datetime import date, timedelta

from calendar_config import load_config

QUESTION_DIR = "data/questions"
ANSWER_DIR = "data/answers"
OUTPUT_PATH = "docs/questions.json"

# Written in this order for every question, regardless of what order its
# own JSON keys were in -- keeps docs/questions.json diffs stable from
# run to run. "answers" isn't listed here -- it's not a field a question
# file itself has, it gets attached separately below once every question
# is loaded.
FIELDS = ["town", "category", "question", "submitter_name", "photos", "posted"]
REQUIRED_FIELDS = ("town", "question", "submitter_name")
LIST_FIELDS = {"photos"}

ANSWER_FIELDS = ["answer", "submitter_name", "posted"]
REQUIRED_ANSWER_FIELDS = ("question_id", "answer", "submitter_name")


def load_answers():
    """Every approved answer, keyed by the question_id it answers.
    A malformed or incomplete answer file is skipped with a warning,
    same as everywhere else -- one bad file shouldn't break the build.
    An answer whose question_id doesn't match any question that's still
    published (expired, held back, or never existed) is silently
    dropped when questions are loaded below, not here -- this function
    doesn't know yet which questions survive."""
    by_question = {}
    for path in sorted(glob.glob(os.path.join(ANSWER_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  WARNING: skipping unreadable answer {path}: {e}", file=sys.stderr)
            continue

        values = {field: (data.get(field) or "").strip() for field in REQUIRED_ANSWER_FIELDS}
        if not all(values.values()):
            print(f"  WARNING: skipping {path}, missing a required field ({REQUIRED_ANSWER_FIELDS})", file=sys.stderr)
            continue

        answer = {field: (data.get(field) or "").strip() for field in ANSWER_FIELDS if (data.get(field) or "").strip()}
        by_question.setdefault(values["question_id"], []).append(answer)

    for answers in by_question.values():
        answers.sort(key=lambda a: a.get("posted") or "")
    return by_question


def load_questions(config, answers_by_question, today=None):
    """Same shape as load_posts() in build_jobs_directory.py /
    build_clubs_directory.py -- a malformed/incomplete/"Other"-town
    file is skipped or held back, an old-enough question expires by
    its "posted" date, and a pinned "example" question is exempt from
    both and always sorts first."""
    today = today or date.today()
    expiry_days = config.get("question_expiry_days", 45)
    questions = []
    held_back = 0
    expired = 0
    for path in sorted(glob.glob(os.path.join(QUESTION_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  WARNING: skipping unreadable question {path}: {e}", file=sys.stderr)
            continue

        question_id = (data.get("id") or "").strip()
        values = {field: (data.get(field) or "").strip() for field in REQUIRED_FIELDS}
        if not question_id or not all(values.values()):
            print(f"  WARNING: skipping {path}, missing id or a required field ({REQUIRED_FIELDS})", file=sys.stderr)
            continue
        if values["town"] == "Other":
            held_back += 1
            continue

        is_example = bool(data.get("example"))
        posted = (data.get("posted") or "").strip()
        if not is_example and posted:
            try:
                posted_date = date.fromisoformat(posted)
                if today - posted_date > timedelta(days=expiry_days):
                    expired += 1
                    continue
            except ValueError:
                pass

        question = {"id": question_id}
        for field in FIELDS:
            if field in LIST_FIELDS:
                raw_value = data.get(field)
                if isinstance(raw_value, list) and raw_value:
                    question[field] = raw_value
                continue
            value = (data.get(field) or "").strip()
            if value:
                question[field] = value
        if is_example:
            question["example"] = True
        question["answers"] = answers_by_question.get(question_id, [])
        questions.append(question)

    # Newest first, same reasoning as every other expiring board.
    questions.sort(key=lambda q: q.get("posted") or "", reverse=True)
    questions.sort(key=lambda q: not q.get("example", False))
    return questions, held_back, expired


def main():
    config = load_config()
    answers_by_question = load_answers()
    questions, held_back, expired = load_questions(config, answers_by_question)

    towns = sorted({q["town"] for q in questions if q["town"] in config["towns"]})
    answered = sum(1 for q in questions if q["answers"])
    print(f"Building Ask the Community: {len(questions)} question(s) ({answered} answered) across {len(towns)} of {len(config['towns'])} official towns")
    if held_back:
        print(f"  ({held_back} question(s) held back -- town unresolved, still \"Other\" in data/questions/)")
    if expired:
        print(f"  ({expired} question(s) expired -- older than {config.get('question_expiry_days', 45)} days, source file left in data/questions/)")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
