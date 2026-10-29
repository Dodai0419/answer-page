---
name: answer-page
description: Answer a hard question with a one-page HTML (cards, flow chart, sequence diagram, status table, callouts) instead of a wall of text. You write a short Markdown draft; the script lays out the diagrams, builds the page and checks the writing (short sentences, plain words). Use when the user asks to explain, compare, or map something, or says "answer with a page / diagram". Small answers stay as plain text.
---

# answer-page

## Step 1: pick the lowest rung that works
- One or two short paragraphs, no structure → answer in plain text. Stop.
- Steps, a comparison, states, or messages between parties → write a draft and render a page.

## Step 2: write the draft (Markdown)
~~~markdown
---
title: TCP three-way handshake
subtitle: How two hosts agree to talk
cols: 3
source: RFC 9293
---
One or two sentences: the answer first.

## A Three-way handshake {span=2 meta="open"}
```sequence
participants: Client, Server
Client -> Server: SYN, seq=x
Server --> Client: SYN+ACK
note Client, Server: ESTABLISHED
```

## B State changes
```flow LR
(CLOSED) -> LISTEN: passive open
SYN_SENT -> *ESTABLISHED
A & B -> {Valid?}
```

## C Flags
| Flag | In handshake |
|---|---|
| SYN | ok steps 1, 2 |

```callout warn Two is not enough
Body text.
```
~~~

Syntax notes: `cols` sets the grid columns and `source` adds a footer. `-->` draws a dashed line. `*Name` highlights a node. Node shapes: `(round)`, `{diamond}`, `[(database)]`, `[box]`. `flow LR` or `flow TB` sets the direction. A table cell that starts with `ok`, `no` or `warn` becomes a colored chip.

Writing rules the checker enforces (warnings, not errors): steps ≤ 20 words, other sentences ≤ 25 words, ≤ 6 sentences per paragraph, no passive voice in numbered steps, plain words (`use` not `utilize`, `before` not `prior to`).

## Step 3: render (from the repo root)
```bash
python answer_page.py draft.md -o answer.html            # page + style warnings
python answer_page.py draft.md --rung auto               # prints plain text if a page would not help
python answer_page.py draft.md --strict                  # exit 1 on style warnings
```
Fix the warnings, render again, then give the user the HTML path. The page is one file, works offline, and follows the system light/dark setting.
