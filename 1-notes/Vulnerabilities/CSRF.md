---
tags:
  - vulnerability
---
# **Cross-site Request Forgery (CSRF)** 

CSRF is a web vulnerability that tricks users into performing unintended actions on a website where they are authenticated, bypassing the same-origin policy.  

**Impact**: Attackers can manipulate user accounts (e.g., change email, password, or transfer funds), potentially gaining full control if the user has privileged access.  

**Conditions for Attack**:  
1. A valuable action (e.g., changing account details).  
2. Cookie-based **session** handling with no additional session validation.  
3. Predictable request parameters (no unknown values).  

**How It Works**:  
An attacker crafts a malicious webpage (e.g., with a hidden form) that submits a request to the vulnerable site. If the victim is logged in, their browser includes session cookies, and the site processes the request as legitimate. Example: A form changing the user’s email to an attacker-controlled address.  

**Delivery**:  
Similar to reflected XSS—hosted on attacker-controlled sites, spread via links, or embedded in popular sites. GET-based CSRF can use simple URLs (e.g., `<img src="vulnerable-site.com/change?email=attacker@evil.com">`).  

**Defenses**:  
1. **CSRF Tokens**: Unique, unpredictable tokens required in requests.  
2. **SameSite Cookies**: Restrict cookies from cross-site requests (Lax by default in Chrome).  
3. **Referer Validation**: Verify request origin (less reliable).  

**Bypassing Defenses**: Possible by exploiting weak token validation, lax SameSite settings, or flawed Referer checks.

---
## **XSS vs CSRF**

**XSS (Cross-Site Scripting)**: Allows attackers to inject and execute malicious JavaScript in a victim's browser, enabling arbitrary actions and data theft.

**CSRF (Cross-Site Request Forgery)**: Tricks users into performing unintended actions on a site where they’re authenticated, without retrieving responses.

**Key Differences**:
- **Impact**: XSS is more severe, allowing attackers to perform any user action and steal data (two-way). CSRF is limited to specific actions and is one-way (no response retrieval).
- **Scope**: XSS exploits any vulnerable function; CSRF often targets unprotected or overlooked actions.

**Can CSRF Tokens Prevent XSS?**
- **Yes, in some cases**: For **reflected XSS**, if a function requires a valid CSRF token and the server rejects invalid tokens, exploitation is blocked since the attacker can’t forge a valid cross-site request.
- **Limitations**:
  - If another site function lacks CSRF protection, reflected XSS can be exploited normally.
  - Exploitable XSS (reflected or stored) can bypass CSRF tokens by requesting a valid token from the site and using it to perform protected actions.
  - **Stored XSS** is unaffected by CSRF tokens, as the malicious script executes directly on the page when visited, within the site’s context.

---
## 1. Bypassing CSRF token validation

**Testing CSRF Tokens:**
1. Remove the CSRF token and see if application accepts request
2. Change the request method.
3. See if csrf token is tied to user session.

**Testing CSRF Tokens and CSRF cookies:**
1. Check if the CSRF token is tied to the CSRF cookie
	- Submit an invalid CSRF token
	- Submit a valid CSRF token from another user
	
2. Submit valid CSRF token and cookie from another user, and if it works, it will be exploitable if you found another way to inject the cookie.

>**Note**: 
	The cookie-setting behavior does not even need to exist within the same web application as the CSRF vulnerability. Any other application within the same overall DNS domain can potentially be leveraged to set cookies in the application that is being targeted, if the cookie that is controlled has suitable scope. For example, a cookie-setting function on `staging.demo.normal-website.com` could be leveraged to place a cookie that is submitted to `secure.normal-website.com`.

>**Note**:
	Adding `SameSite=None` tells the browser: “Hey, it’s okay to send this cookie even in cross-origin requests.”

---
## 2. Bypassing SameSite cookie restrictions

### What Defines a "Site"?

A **site** is defined as:
- **TLD+1** (e.g., `example.com` in `app.example.com`).
- **Subdomains** are part of the same site.
- **Scheme matters**: `http` to `https` is treated as **cross-site** by browsers.

```python
https://app.example.com
  |      |    |      |
  |      |    |      +-- TLD (.com)
  |      |    +--------- +1 (example)
  |      +-------------- Subdomain (app)
  +--------------------- Scheme (https)
```
### What's the difference between a site and an origin?

#### Site

| Origin A                      | Origin B                        | **"Same-site" or "cross-site"?**             |
| ----------------------------- | ------------------------------- | -------------------------------------------- |
| `https://www.example.com:443` | `https://www.evil.com:443`      | Cross-site: different domains                |
|                               | `https://login.example.com:443` | Same-site: different subdomains don't matter |
|                               | `http://www.example.com:443`    | Cross-site: different schemes                |
|                               | `https://www.example.com:80`    | Same-site: different ports don't matter      |
|                               | `https://www.example.com:443`   | Same-site: exact match                       |
|                               | `https://www.example.com`       | Same-site: ports don't matter                |

#### Origin

| Origin A                      | Origin B                        | **"Same-origin" or "cross-origin"?**            |
| ----------------------------- | ------------------------------- | ----------------------------------------------- |
| `https://www.example.com:443` | `https://www.evil.com:443`      | Cross-origin: different domains                 |
|                               | `https://example.com:443`       | Cross-origin: different subdomains              |
|                               | `https://login.example.com:443` | Cross-origin: different subdomains              |
|                               | `http://www.example.com:443`    | Cross-origin: different schemes                 |
|                               | `https://www.example.com:80`    | Cross-origin: different ports                   |
|                               | `https://www.example.com:443`   | Same-origin: exact match                        |
|                               | `https://www.example.com`       | Same-origin: implicit port number (443) matches |

### What is SameSite?

SameSite is a cookie attribute that controls whether cookies are sent with cross-site requests. It's designed to reduce the risk of CSRF attacks by limiting when cookies are included.

### Why it matters

- Without SameSite, cookies are sent with all requests, including those from third-party sites.
- SameSite allows developers to specify which cross-site requests should include cookies.

### SameSite Attribute Options

**Strict**

- Cookie is not sent with any cross-site request.
- Most secure option.
- Can break user experience where cross-site interaction is expected.

**Lax**

- Cookie is sent only on top-level GET requests (e.g., clicking a link).
- Not sent on POST requests, iframes, or background scripts.
- Provides basic CSRF protection with minimal usability impact.

>Since 2021, Chrome defaults cookies to `SameSite=Lax` if not specified.

**None**

- Cookie is sent with all requests, including third-party.
- Must be used with the `Secure` flag (HTTPS only).
- Useful for third-party content like analytics, but risky for sensitive data.

>Cookies set with `SameSite=None` or without explicit restrictions should be reviewed to determine their necessity.

---
### Bypassing SameSite Lax restrictions using GET requests

```html
<input type="hidden" name="_method" value="GET">
```

---
### Bypassing SameSite restrictions using on-site gadgets

Client-side redirects (e.g. DOM-based) can bypass `SameSite=Strict` if triggered from a page already on the target domain.  

Server-side redirects **won’t bypass** the restriction **if the initial navigation was cross-site**, as the browser tracks the origin of the full redirect chain.

---







---

**References**
- https://portswigger.net/web-security/csrf
- https://web.dev/articles/same-site-same-origin