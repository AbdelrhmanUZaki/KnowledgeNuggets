### Broken Access Control

**What it is:**  
Broken Access Control occurs when an application fails to properly enforce what authenticated users are allowed to do (authorization). This can let users access or modify data or features beyond their intended permissions.

**Key Concepts:**

- **Authentication** = confirms _who_ the user is
- **Authorization** = determines _what_ they can do  
	- Broken access control issues are **authorization** failures.
	
---
### Example Scenario: Unauthorized Grade Change

A college student discovers that their university’s grade management API lacks proper authorization checks. They send this direct HTTP request to alter their own grade:

```http
PATCH /grades HTTP/2
Host: api.grades.patch.edu
Authorization: Basic [credentials]
Content-Length: 65

{
  "subjectID": 1293,
  "studentID": 20223948,
  "grade": "A"
}
```

Since the server doesn’t verify the user’s role (e.g. student vs. teacher), it accepts the request and updates the grade — despite the action being restricted to teachers.

---
### Common Issues:

- No server-side role validation
- Insecure Direct Object References (IDOR)
- Relying solely on UI restrictions
    
---
### Mitigation Strategies:

- Enforce **role-based access control (RBAC)** in backend logic
- Never trust user input to define permissions
- Example fix:
	```javascript
	// Allow only the authenticated user to view their data
	if (requestedUserId !== currentUser.id) {
	  return res.status(403).send('Access Denied');
	}
	
	// Only teachers can modify grades
	if (currentUser.role !== 'teacher') {
	  return res.status(403).send('Access Denied');
	}
	```

- Regularly audit and test access control logic
- Follow [OWASP's Authorization Cheat Sheet Series](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
    
---
### Why it matters:  
Broken Access Control is ranked **#1 in the OWASP Top 10 (2021)** due to its frequency and critical impact, making it a top priority for secure application development.

---
### Suggested Reading

Resources not directly used in this summary but useful for further learning:
- [Authorization - OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) 
- [A01 Broken Access Control - OWASP Top 10:2021](https://owasp.org/Top10/A01_2021-Broken_Access_Control/)
- [WSTG - Authorization Testing](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/05-Authorization_Testing/README)

---
### References

Sources directly referenced in this summary:
- [What is broken access control | Tutorial & Examples | Snyk Learn](https://learn.snyk.io/lesson/broken-access-control/?ecosystem=php)
	- Check the examples in [C++, Go, JavaScript, PHP, Python] to see how the issue applies across languages.