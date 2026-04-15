# Edison Gotchas

- **Never hardcode the API key.** Always `os.environ["EDISON_API_KEY"]`.
- **Non-interactive shells** (cron, subprocess, CI) won't inherit shell-profile exports. Pass the env explicitly, source the user's profile first, or load a `.env`.
- **`run_tasks_until_done` blocks** with internal polling. LITERATURE_HIGH and ANALYSIS can take many minutes — don't impose aggressive timeouts.
- **Kosmos is not API-accessible** despite appearing in agent docs. Use the web platform.
- **Response schema is undocumented.** Inspect return objects before asserting fields. Artifacts live under `job_result.environment_frame["state"]["info"]["output_data"]`.
- **Async is the full-featured path** for storage operations — sync API doesn't cover every file op.
- **Enumerate `JobNames` at runtime** to see what your installed version supports; don't assume from docs.
- **PaperQA2, Aviary, LDP** are separate OSS packages on the same docs site, not part of `edison-client`.
