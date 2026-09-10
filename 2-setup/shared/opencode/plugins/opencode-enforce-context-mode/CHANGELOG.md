# Changelog

All notable changes to this project will be documented in this file.

## [1.0.12] - 2026-04-30

### Changed
- **Optimization**: Moved guard checks before prompt construction in `experimental.chat.messages.transform` hook. Avoids unnecessary string concatenation when prompt is already injected. (GitHub #1)
 
## [1.0.11] - 2026-04-22
 
### Fixed
- **Repository Cleanup**: Removed stale `package-lock.json` and legacy dev-dependencies to ensure a lean, production-ready package.
 
 ## [1.0.10] - 2026-04-22

### Fixed
- **Documentation Clarity**: Refined README to focus on shell environment variables and removed deprecated `opencode.json` configuration examples.
- **Cleanup**: Removed `opencode.json.example` to prevent confusion with unsupported configuration methods.

## [1.0.9] - 2026-04-22

### Added
- Proactive AI Guidance: Implemented `experimental.chat.messages.transform` hook to inject structural environment constraints before tool execution, ensuring immediate AI compliance.
- Semantic Mapping: Enhanced redirection logic to suggest specific `context-mode` replacements (e.g., `ctx_execute_file` for `cat`, `ctx_fetch_and_index` for `webfetch`).

### Fixed
- Bypass Prevention: Resolved a bug where case-sensitive tool names (e.g., `WebFetch`) could bypass enforcement.
- UX & "Anti-Paranoia": Wrapped all directives and errors in `<environment_constraints>` and `<tool_execution_error>` XML tags to look like formal system responses, preventing AI suspicion of prompt injection.
- Standardized Enforcement: Re-worded error headers to use official-sounding `SYSTEM DIRECTIVE` blocks for higher compliance.

## [1.0.8] - 2026-04-22

### Changed
- Renamed all environment variables to use an `OPENCODE_` prefix (`OPENCODE_ENFORCE_MODE`, `OPENCODE_ALLOW_PATTERNS`, `OPENCODE_ALLOW_BASH_CMDS`, `OPENCODE_BLOCK_BASH_CMDS`) to prevent collisions and improve clarity.
- Clarified in README that environment variables are strictly optional overrides.
- Migrated GitHub Actions CI workflow to use `oven-sh/setup-bun` instead of Node/npm.

## [1.0.7] - 2026-04-22

### Added
- Permanent rigorous test suite covering bash syntax edge cases.
- `ENFORCE_ALLOW_COMMANDS`: add bash commands to allowed list.

### Changed
- Replaced error messages with highly aggressive, compliance-forcing warnings.
- Recommended `force=true` argument when prompting AI to use `ctx_fetch_and_index`.
- Migrated test framework from `vitest` to `bun test` for significantly faster execution and zero dev dependencies.

### Removed
- Removed `warn` / `dry-run` modes and the `ENFORCE_LOG` environment variable to massively simplify the codebase and avoid user confusion. The plugin now operates strictly in enforce mode (1) or disabled mode (0).

### Fixed
- Fixed crash when plugin was disabled (`ENFORCE_CONTEXT_MODE=0`) by returning an empty object instead of `null` to comply with OpenCode plugin architecture.
- Hook signature compatibility: Plugin now correctly handles input tools natively passed in either `input` or `output` arguments.
- Bash regex parser: Fixed bug where blocked commands were missing if they appeared at the very end of a string or were separated by `|`, `&`, or `;`.
- Robust path bypass prevention: Blocked AI from bypassing filters using absolute or relative paths (e.g., `/usr/bin/curl` or `./curl`).
- Bypasses prevented: Correctly blocks wrappers like `sudo`, `env`, `time`, etc.
- Case-sensitivity bug: `Bash` is now treated identically to `bash`.

## [1.0.6] - 2026-04-22

### Changed
- README: cleaner and simpler

## [1.0.5] - 2026-04-22

### Changed
- README: clearer messaging - "blocks" instead of "redirects"
- Tool table: shows correct alternatives

## [1.0.4] - 2026-04-22

### Fixed
- README: license badge

## [1.0.3] - 2026-04-22

### Added
- README: link to OpenCode issue #14808

## [1.0.2] - 2026-04-22

### Fixed
- package.json: repository and homepage URLs

## [1.0.1] - 2026-04-22

### Fixed
- README links

## [1.0.0] - 2026-04-22

### Added
- Initial release
- Mode system: disabled, dry-run, warn, hard block
- Tool enforcement for: grep, glob, webfetch, websearch, codesearch, bash, Read
- Configurable ENFORCE_ALLOW allowlist (supports all tool args: command, pattern, filePath, url, query)
- Configurable ENFORCE_BLOCK for bash sub-commands
- ENFORCE_LOG for verbose logging
- 31 unit tests including bug regression tests
- Word-boundary matching for bash sub-commands (prevents false positives in paths)
- Search-term-only analysis detection for Read tool (prevents false positives in filenames)