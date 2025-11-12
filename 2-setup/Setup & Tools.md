- [Obsidian](https://obsidian.md/) (Note-taking app)
- [Linux Setup](Linux%20Setup.md)

- Fuzzing:
	- [Feroxbuster: A fast, simple, recursive content discovery tool written in Rust.](https://github.com/epi052/feroxbuster)
	```
	curl -sL https://raw.githubusercontent.com/epi052/feroxbuster/main/install-nix.sh | bash -s $HOME/.local/bin
	```
	- [Dirsearch: Web path scanner](https://github.com/maurosoria/dirsearch)
	- FFUF
		- `brew install ffuf`
		- Without its default status code to avoid missing status codes for APIs like `405` or `415`
		- `-fs`: Filter trash response by size with
		- `-ac`: Automatic filtering, so you don't have to use `-fs 559`, for example.
	- Nuclei
	  `brew install nuclei`
	
- Burp Extensions: 
	- Auth Analyzer
	- JWT Editor
	- Inql
	- Upload scanner
	- Content type converter
	
- Web Extensions:
	- [Wappalyzer - Technology profile](https://chromewebstore.google.com/detail/wappalyzer-technology-pro/gppongmhjkpfnbhagpmjfkannfbllamg)
	- [Fake Filler](https://chromewebstore.google.com/detail/bnjjngeaknajbdcgpfkgnonkmififhfo?utm_source=item-share-cb)
	- Firefox:
		- [pwnfox](https://addons.mozilla.org/en-US/firefox/addon/pwnfox/) for proxy and its [jar file](https://github.com/yeswehack/PwnFox/releases/tag/v1.0.3) as an extension for Burp Suite to color the requests in the browser and in Burp.
	- Brave:
		- SwitchyOmega for proxy