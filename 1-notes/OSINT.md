---
tags:
  - osint
---
# OSINT

- Search engines (Advanced Search)
	- https://www.google.com/advanced_search
	- https://support.microsoft.com/en-us/topic/advanced-search-options-b92e25f1-0085-4271-bdf9-14aaea720930
	- https://duckduckgo.com/duckduckgo-help-pages/results/syntax

- A powerful **Nuclei** command for OSINT targeting:
	```sh
	nuclei -tags osint -var user="YourVictim@redacted.com" -esc -silent
	```
- Useful OSINT resources:
	- [https://pipl.com/](https://pipl.com/)
	- [OSINT Framework](https://osintframework.com/)
- Google Dorking
	- https://github.com/spekulatius/infosec-dorks
- https://shodan.io
- https://en.fofa.info/
- wappalyzer
- Wayback Machine
	- https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md
- GitHub  & Gitlab
- S3 Buckets
	- Format: `http(s)://{name}.s3.amazonaws.com`
	- Could be found via the target's webpage source, GitHub repos, or guessing like: {target-name}-assets, {target-name}-www, {target-name}-public, {target-name}-private



---

References:
- https://tryhackme.com/room/searchskills