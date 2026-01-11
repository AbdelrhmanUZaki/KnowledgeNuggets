---
tags:
  - vulnerability
---
## DOM-Based Open Redirection

### What is it?

A vulnerability where client-side JavaScript reads user-controlled input (e.g., from `location.hash` or `location.search`) and redirects the browser without validation.

**Example:**

```js
let url = /https?:\/\/.+/.exec(location.hash);
if (url) location = url[0];
```

---

### Impact

- Enables phishing using legitimate-looking URLs.
- Can lead to JavaScript injection via `javascript:` schemes.
- Exploitable even with HTTPS and valid domains.

---

### Common Vulnerable Sinks

```
location
location.host
location.hostname
location.href
location.pathname
location.search
location.protocol
location.assign()
location.replace()
open()
element.srcdoc
XMLHttpRequest.open()
XMLHttpRequest.send()
jQuery.ajax()
$.ajax()
```

---

### Prevention

- Avoid using untrusted input for redirection.
- Sanitize and validate any navigation logic.
- Prefer internal path redirects with a whitelist.

---

**References**
- https://portswigger.net/web-security/dom-based/open-redirection