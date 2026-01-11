# Methedology

### - Every single piece of information is an attack surface

### - [Godfather Orwa](Godfather%20Orwa.md)

### - Notes
- Try to find an Exploit for known CVEs in your application.
- Always view the page source
- Multiple steps to perform an action mean increased complexity in implementing this feature, so try to check for vulnerabilities in that flow.
- Press each button, even if it looks unimportant, and don't forget to see the background requests that it made in Burp.
- Check request and response headers.
- Check the User access matrix.
- Check the postman collection if available.
- Check the website docs to understand it deeply.
- To view the cached data again, remove the headers `If-None-Match` and `If-Modified-Since`.
- for browsers check
	- **View Source** - Use your browser to view the human-readable source code of a website.
		- HTML comments are dangerous 
		- Deep dive into all URLs and look inside all dirs you found
	- **Inspector** - Learn how to inspect page elements and make changes to view usually blocked content.
		- You may need to edit some CSS to display what is hidden or display what is blocked until you are a premium customer for the target, or remove the attached "class" to the blocked div section
	- **Debugger** - Inspect and control the flow of a page's JavaScript
		- Many times when viewing JavaScript files, you'll notice that everything is on one line, which is because it has been minimised, which means all formatting ( tabs, spacing, and newlines ) has been removed to make the file smaller
		- We can return some of the formatting by using the "Pretty Print" option, which looks like two braces { } to make it a little more readable
		- You could press on the line number for a JS file to make a breakpoint, then refresh the page to reload, and it will stop before executing this line.
	- **Network** - See all the network requests a page makes.
		- Note about the new request that the website made when you take an action on the website, it may reveal secret data

### Content discovery
#### 1. Manual Content Discovery 

- /robots.txt
- /sitemap.xml
- https://wiki.owasp.org/index.php/OWASP_favicon_database
	- If the target app has a favicon, get the md5sum of the favicon and search for it in the OWASP favicon DB to know which framework is used. Command may look like:
	  ```sh
	  curl https://domain.com/path/to/favicon.ico | md5sum
	    ``` 
- HTTP Headers
	- To get some headers like `Server` or `X-Powered-By` using a command like `curl https://domain.com -v`
#### 2. [[OSINT]]
#### 3. Automated Discovery 
- Seclists using `ffuf`, `dirb`, or `gobuster`
	- `ffuf -w /usr/share/wordlists/SecLists/Discovery/Web-Content/common.txt -u http://10.81.180.184/FUZZ`
	- `dirb http://10.81.180.184/ /usr/share/wordlists/SecLists/Discovery/Web-Content/common.txt`
	- `gobuster dir --url http://10.81.180.184/ -w /usr/share/wordlists/SecLists/Discovery/Web-Content/common.txt`

### Authentication Bypass


---

References:
- [OrwaGodFather Methodology](https://www.youtube.com/playlist?list=PLiLvsecrejRhQ7lOGgZSga47Jwhf5YXwD)
- https://tryhackme.com/room/contentdiscovery