- [Obsidian](https://obsidian.md/) (Note-taking app)
- [Linux Setup](Linux%20Setup.md)
- warp terminal
	- Offers some features like a very big screen for all outputs that was printed in the terminal, also copies the output of a command fast
- **Fuzzing**:
	- **Content discovery**
		- [FFUF](https://github.com/ffuf/ffuf) 
			- Without its default status code to avoid missing status codes for APIs like `405` or `415`
			- `-fs`: Filter trash response by size with
			- `-ac`: Automatic filtering, so you don't have to use `-fs 559`, for example.
		- [Feroxbuster](https://github.com/epi052/feroxbuster)
		- [Dirsearch](https://github.com/maurosoria/dirsearch) 
			```
				git clone https://github.com/maurosoria/dirsearch.git --depth 1 && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
			```
		- [gobuster](https://github.com/OJ/gobuster)
	- **Parameter discovery**
		- Arjun
	- **Cloud enumeration**
		- cloud_enum (But look for Nuclei also)
	- **Vulnerability scanner**
		- Nuclei 
		  `echo 'export PATH=$PATH:$HOME/go/bin' >> ~/.bashrc && source ~/.bashrc`
-  **Wordlists**
	- [https://github.com/six2dez/OneListForAll](https://github.com/six2dez/OneListForAll) (Rockyou for web fuzzing)
	- [https://github.com/danielmiessler/SecLists](https://github.com/danielmiessler/SecLists)
	
- **Burp Extensions**: 
	- Auth Analyzer
		- In cases like "DELETE" requests, drop the original request so the object remains, and the extension can replay it to test normal-user access.
	- JWT Editor
	- Inql
	- Upload scanner
	- Content type converter
	
- **Web Extensions**:
	- [Wappalyzer - Technology profile](https://chromewebstore.google.com/detail/wappalyzer-technology-pro/gppongmhjkpfnbhagpmjfkannfbllamg)
	- [Fake Filler](https://chromewebstore.google.com/detail/bnjjngeaknajbdcgpfkgnonkmififhfo?utm_source=item-share-cb)
	- Firefox:
		- [pwnfox](https://addons.mozilla.org/en-US/firefox/addon/pwnfox/) for proxy and its [jar file](https://github.com/yeswehack/PwnFox/releases/tag/v1.0.3) as an extension for Burp Suite to color the requests in the browser and in Burp.
	- Chromium:
		- https://github.com/bscript/rep: Burp-style HTTP Repeater
		- SwitchyOmega for proxy
- Metasploit