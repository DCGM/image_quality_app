# Preserve text newlines in classification UI

## What changed

- Updated the classification text display to preserve embedded newline characters while still wrapping long text safely.

## Why

Uploaded text passages can contain meaningful line breaks. HTML collapses whitespace by default, so annotators were seeing passages without their original line structure.

## Decisions

- Used CSS `white-space: pre-wrap` on the text card so newline characters are rendered and normal wrapping remains available.
