---
description: Add a READ or ACT tool to the assistant, docs first, with tests.
argument-hint: what the tool should do
---

The owner wants this tool: $ARGUMENTS

Follow prompts/new-tool.md. Ask me for any {placeholder} you cannot infer from docs/decisions.md.
If the tool changes anything, it is ACT. If you are unsure, it is ACT.
Do not finish until `make check` passes and you have shown me the approval text an ACT tool will display.
