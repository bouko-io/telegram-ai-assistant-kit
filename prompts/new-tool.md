Add a tool to starter/tools.py.

What it does: {what_it_does}
Kind: {READ or ACT}  (if it changes anything at all, it is ACT)
Command or API it uses: {command_or_api}
Allowed arguments: {allowlist}

Before writing code:
1. If it calls an API, read the official docs and tell me: auth, requests per minute and per day,
   free-tier limits (date ranges, fields, resources), whether errors come back as HTTP 200 with an error
   in the body, pagination. Make one real request only if I agree, and show me the response shape.
2. Show me the tool's name, description and input_schema.

Then:
- Arguments must be enums or match a strict pattern AND be checked against an allowlist in code.
- subprocess with a fixed argv list, timeout, no shell. Trim output to ~2000 characters.
- ACT: respect ACT_DRY_RUN, give a describe() line that says exactly what will happen.
- Comment each limit you found at the line it constrains, with "(docs read YYYY-MM-DD)".
- Tests with fakes: READ runs; ACT waits for approval, approve runs, decline never runs,
  a bad argument is refused.
- Run make check and show the output.
