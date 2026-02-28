# Conversation Quality Report (messages.csv)

Date: 2026-02-28  
Source: `/home/alikheiri/Downloads/messages.csv`

## Snapshot

- Total rows: `1017`
- Roles:
  - `user`: `387`
  - `assistant`: `263`
  - `admin`: `350`
  - empty role: `17`
- Assistant non-empty messages: `259`

## Key Risk Signals

- Generic assistant replies: `150 / 259` (`57.9%`)
- Conversations with repeated assistant loop segments: `3`
- User messages followed by assistant within 5 rows: `317 / 387` (`81.9%`)
- Most repeated templates include:
  - `سلام! چطور می‌توانم به شما کمک کنم...` (45)
  - `سلام! چطور می‌توانم به شما کمک کنم...` variant (34)
  - `به نظر می‌رسد که شما عکسی ارسال کرده‌اید...` (26)

## Root Causes (From Real Data)

- High template overuse in greeting/discovery messages.
- Over-fallback to generic clarification instead of contextual product guidance.
- Partial unresolved conversation flow (user speaks, assistant not always following quickly).

## Anti-Error Package (Implemented)

- Contextual fallback rewrite for generic outputs.
- Image-first product matching path using vision analysis + search terms.
- Stronger loop/generic detection and response rewriting.
- Policy memory channel for admin rules/events/campaigns with priority levels.
- Conversation quality API for monitoring and action planning.

## How To Regenerate

```bash
python3 scripts/analyze_messages.py /home/alikheiri/Downloads/messages.csv --json-out reports/conversation_quality_report.json
```
