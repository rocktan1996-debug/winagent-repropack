# Diagnostic issue report

> **MANUAL REVIEW REQUIRED — Review before sharing.**

Unknown private information may remain. Inspect this draft before disclosure.
Independent project; not affiliated with or endorsed by OpenAI.
Symptoms are observed text, not a verified diagnosis.

## Environment

- Client: generic
- Generator: WinAgent ReproPack 0\.1\.0rc1

## Observed symptom summary

- Total lines: 9
- Matched event lines: 6
- Unknown or incomparable timestamp lines: 0
- Local/unzoned timestamp lines (timezone unknown): 0
- Multiple-category lines counted once: 1

| Category | Count | First line | Last line | Saved line numbers | First seen | Last seen |
| --- | ---: | ---: | ---: | --- | --- | --- |
| remote\_compact\_failure | 1 | 4 | 4 | 4 | 2026\-10\-22T01:01:30\+08:00 | 2026\-10\-22T01:01:30\+08:00 |
| stream\_disconnect | 1 | 1 | 1 | 1 | 2026\-10\-22T01:00:00\+08:00 | 2026\-10\-22T01:00:00\+08:00 |
| capacity | 2 | 2 | 3 | 2, 3 | 2026\-10\-22T01:00:10\+08:00 | 2026\-10\-22T01:01:00\+08:00 |
| reconnect\_loop | 1 | 5 | 5 | 5 | 2026\-10\-22T01:02:00\+08:00 | 2026\-10\-22T01:02:00\+08:00 |
| timeout | 1 | 6 | 6 | 6 | 2026\-10\-22T01:03:00\+08:00 | 2026\-10\-22T01:03:00\+08:00 |

Time bounds require comparable explicit offsets for every event in a category.
Saved line numbers are capped at 20; counts and last observed line remain complete.

## Doctor summary

- Included: yes; schema: 1
- Codex version: 0\.0\.0\-dev\.1\+build\.1
- Overall status: warning
- Checks: ok=2, warning=1, fail=1

## Optional sanitized symptom fragments

No excerpts included.

## Steps to reproduce

[USER TO FILL]

## Expected behavior

[USER TO FILL]

## Actual behavior

[USER TO FILL]

## What I tried

[USER TO FILL]

## Limits and privacy checklist

- Regex matches only some known symptoms and may miss or misclassify other formats.
- No inferred cause, global outage, severity, subscription or fix is established.
- [ ] Inspect names, paths, URLs, credentials and proprietary information.
- [ ] Fill in only reproduction details you can personally verify.
- [ ] Remove anything you do not intend to disclose.

**MANUAL REVIEW REQUIRED — Review before sharing.**
