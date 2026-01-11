---
tags:
  - checklist
---
- [ ] ID Testing Methods:
	- [ ] Replace IDs in URLs, headers, and body: `/users/01` --> `/users/02`
	- [ ] Test for parameter pollution: `users=01` --> `users=01&users=02`
	- [ ] Use wildcards to test for disclosure: `/users/01*` or `/users/*`

- [ ] Endpoint Analysis:
	- [ ] Some functions may be not in the UI, but its API works for all roles.
	- [ ] Check older API versions:` /api/v3/users/01` --> `/api/v1/users/02`
	- [ ] Add extensions: `/users/01` --> `/users/02.json`
	- [ ] Use Burp Intruder to switch HTTP methods: `POST` --> `GET, PUT, PATCH, DELETE`

- [ ] Header Validation:
	- [ ] Inspect headers like Referrer for ID validation.
		GET `/users/02` --> 403 Forbidden (with Referrer: example.com/users/01)
		GET `/users/02` --> 200 OK (with Referrer: example.com/users/02)

- [ ] Encrypted IDs:
	- [ ] Decode encrypted IDs using tools like hashes.com.

- [ ] GUID Analysis:
	- [ ] Swap GUIDs with numeric IDs or emails:
		- `/users/1b04c196–89f4–426a-b18b-ed824ce283` --> `/users/02` or `/users@domain.com`
	- [ ] Test common GUIDs: `00000000–0000–0000–0000–000000000000` or `11111111–1111–1111–1111–111111111111`
	- [ ] Perform `GUID enumeration` via Google Dorks, GitHub, Wayback, or Burp.

- [ ] 403/401 Response Handling:
	- [ ] Test bypassing: Send 50–100 requests with different IDs (/users/01 --> /users/100).
	- [ ] Double-check blocked requests — actions may still occur.

- [ ] Advanced Techniques:
	- [ ] Look for Blind IDORs by analyzing features like export files or alerts.
	- [ ] Chain IDOR vulnerabilities with XSS for account takeover.


---
### References

- [💡 The Ultimate IDOR Testing Checklist 🚀 | by Muhammet ALGAN | Jan, 2025 | Medium](https://medium.com/@muhammetalgan3547/the-ultimate-idor-testing-checklist-ba4a7c094def)