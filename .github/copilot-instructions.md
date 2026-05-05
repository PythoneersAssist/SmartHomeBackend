# Project Guidelines

## Tool Failures
- When a tool call, command, or validation step fails with a recoverable error, surface the error clearly, fix the input or code, and retry the same operation.
- Do not stop after one failed attempt if the failure can be corrected locally.
- Only ask the user for help when the failure is ambiguous, needs a new decision, or cannot be recovered automatically.
