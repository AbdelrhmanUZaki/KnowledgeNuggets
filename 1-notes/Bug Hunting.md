# Bug Hunting


- Subdomains 
	- Alert of new subdomains https://github.com/yassineaboukir/sublert (Requires VPS )
	- https://crt.sh/
	- `site:*.domain.com -site:www.domain.com`
	- Bruteforce
	- OSINT tools like (with its apis to get better results)
		- Subfinder
		- amass
		- sublist3r
	- Virtual Hosts 
		- There may be hidden dev versions of administration portals or applications that don't have a public DNS result 
		  ```sh
		  ffuf -w /usr/share/wordlists/SecLists/Discovery/DNS/namelist.txt -H "Host: FUZZ.acmeitsupport.thm" -u http://MACHINE_IP
		  ```
		- 