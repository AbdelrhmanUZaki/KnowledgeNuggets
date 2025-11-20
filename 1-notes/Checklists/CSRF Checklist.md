# **Cross-site Request Forgery (CSRF)** 

**Conditions for Attack**:  
1. A valuable action (e.g., changing account details).  
2. Cookie-based **session** handling with no additional session validation.  
3. Predictable request parameters (no unknown values).  

## 1. Bypassing CSRF token validation

### 1.1. Testing CSRF Tokens:
1. Remove the CSRF token and see if the application accepts the request
2. Change the request method.
3. See if the CSRF token is tied to the user session.

### 1.2. Testing CSRF Tokens and CSRF cookies:
1. Check if the CSRF token is tied to the CSRF cookie
	- Submit an invalid CSRF token
	- Submit a valid CSRF token from another user
	
2. Submit a valid CSRF token and cookie from another user, and if it works, it will be exploitable if you find another way to inject the cookie.

---
## 2. Bypassing SameSite cookie restrictions

### 2.1. Bypassing SameSite Lax restrictions using GET requests

If the app honors method **overrides** (e.g., Symfony’s `_method=GET`), an attacker can submit a POST form that the server treats as GET; browsers send cookies on top-level GET navigations, enabling CSRF.
```html
<form action="https://vulnerable-website.com/account/transfer-payment" method="POST"> 
<input type="hidden" name="_method" value="GET">
<input type="hidden" name="recipient" value="hacker">
<input type="hidden" name="amount" value="1000000"> </form>`
```

### 2.2. Bypassing SameSite restrictions using on-site gadgets

A same-site request can be created via a client-side redirect that builds its target from attacker-controlled input. 








---

**References**
- https://portswigger.net/web-security/csrf
- https://web.dev/articles/same-site-same-origin