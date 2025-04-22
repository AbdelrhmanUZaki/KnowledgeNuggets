### What is HSTS?

**HTTP Strict Transport Security (HSTS)** is a security mechanism that enforces HTTPS-only communication by instructing browsers to reject any HTTP connections.

### Purpose:

- Prevents:
    
    - Protocol downgrade attacks (e.g., SSL stripping)
        
    - Cookie hijacking over HTTP
        
    - Passive data leakage via unencrypted links
        

### How It Works:

- Server sends `Strict-Transport-Security` header over HTTPS.
    
- Browser remembers this and refuses future HTTP connections to that domain.
    

### Header Example:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

### Key Considerations:

- **Absence of HSTS** is a misconfiguration that allows downgrade attacks.
    
- **Short `max-age` values** or **missing `includeSubDomains`** weaken protection.
    
- **Preload not enabled** means the site is vulnerable during first connection.
    
- **Redirect-only HTTPS** without HSTS is insecure—still susceptible to MITM attacks.