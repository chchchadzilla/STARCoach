---
description: AI rules derived by SpecStory from the project AI interaction history
applyTo: *
---

## PROJECT OVERVIEW

This file defines all project rules, coding standards, workflow guidelines, references, documentation structures, and best practices for the AI coding assistant.

## CODE STYLE

[To be defined]

## FOLDER ORGANIZATION

[To be defined]

## TECH STACK

[To be defined]

## PROJECT-SPECIFIC STANDARDS

[To be defined]

## WORKFLOW & RELEASE RULES

[To be defined]

## REFERENCE EXAMPLES

[To be defined]

## PROJECT DOCUMENTATION & CONTEXT SYSTEM

[To be defined]

## DEBUGGING

When encountering `OpenRouter error 401: {"error":{"message":"User not found.","code":401}}`:

1.  Verify the OpenRouter API key. This error means the OpenRouter API key is invalid or expired. The bot *is* hearing the user (transcription works fine), but it can't generate a response because every call to OpenRouter fails with a 401 authentication error.
2.  Ensure the API key is valid and has not expired at [https://openrouter.ai/keys](https://openrouter.ai/keys).
3.  Update the `.env` file with the correct, new API key:

```
OPENROUTER_API_KEY=sk-or-v1-YOUR_NEW_KEY_HERE
```

4. Restart the bot after updating the `.env` file.
   This error indicates an invalid or expired OpenRouter API key. Generate a new, valid key at [openrouter.ai/keys](https://openrouter.ai/keys) and update the `OPENROUTER_API_KEY` in the `.env` file.

When the analysis portion fails because the embed size exceeds maximum size of 6000:

1. Ensure the embed size does not exceed 6000 characters. The `_enforce_embed_limit` function in `src/utils/embeds.py` handles truncation, but verify its correct implementation.
2.  If truncating the embed sacrifices too much data, split the report across multiple embeds (Part I and Part II) instead. Update `create_report_embed` in `embeds.py` to return a list of embeds, and update the caller in `voice.py` to send multiple embeds.
   `create_report_embeds()` now builds all fields as tuples first, then tries to fit them in one embed. If the total exceeds 5800 chars, it distributes fields across multiple embeds titled **"Part 1/2"**, **"Part 2/2"**, etc. No data is truncated — every field makes it into one of the embeds.
   -   **`voice.py`** — Sends each embed in the list sequentially.
   -   **`admin.py`** — Same treatment for the `!reanalyze` command.

When encountering `LLM request failed: Chunk too big`:

1. The response chunks from OpenRouter's streaming API exceed aiohttp's default content read size.
2. Use `response.content.iter_any()` with proper line-based SSE parsing.

## FINAL DOs AND DON'Ts

[To be defined]