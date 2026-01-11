# Transport Layer Security (TLS)

## 1. Why TLS Exists

Early Internet protocols were plaintext: anyone on the path could read, alter, or forge traffic. TLS was created to provide three core security guarantees over untrusted networks:

|Goal|What it means in practice|
|---|---|
|**Confidentiality**|Outsiders cannot read the data in transit.|
|**Integrity**|Alterations are detected instantly.|
|**Authentication**|The peer you reach really owns the domain/service.|

---

## 2. Trust Foundations: Certificates and Trust Stores

### 2.1 Certificate Authorities (CAs)

A CA issues a **certificate** that binds _“this public key belongs to this domain/organization”_.  
Browsers and operating systems ship with a list of “root” CAs they already trust.

### 2.2 Trust Stores in Practice

|Platform|Where trust anchors live|Notes|
|---|---|---|
|**Windows**|_Certificate Manager_ (MMC → Certificates snap-in) under **Trusted Root Certification Authorities**, **Intermediate CAs**, and **Personal** stores|.NET, Chrome, Edge, Outlook, and most native apps rely on this store.|
|**Firefox, Java, some VPNs**|Ship an **independent** trust store|Firefox maintains its own list of trusted CAs.|

---

## 3. How a Website (like `google.com`) Obtains a Certificate

1. **Generate a key pair** – The site generates a private key and corresponding public key.
    
2. **Create a Certificate Signing Request (CSR)** – This includes the public key and domain name; it's submitted to a CA.
    
3. **Domain validation** – The CA (e.g., DigiCert, Let’s Encrypt) verifies the requester controls the domain via DNS, HTTP challenge, or email.
    
4. **Certificate issuance** – The CA signs and returns a certificate binding the domain to the public key.
    
5. **Deployment** – The certificate and any intermediates are installed on the server to enable HTTPS.
    

---

## 4. Key Material at Each Party

| Actor      | **Keeps (Private Keys)**                                                                                                                           | **Shares (Public Keys)**                                                                                       |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Server** | - A **long-term private key** (proves identity via certificate).<br>- An **ephemeral private key** (per-session key exchange for forward secrecy). | - **Certificate public key** (identity verification).<br>- **Ephemeral public key** (for secure key exchange). |
| **Client** | - An **ephemeral private key** (used in the session key exchange).                                                                                 | - **Ephemeral public key** (sent to the server).                                                               |

> Public keys are mathematically derived from private keys through one-way cryptographic functions, making it computationally infeasible to reverse. Sharing public keys is safe and essential for encrypted communication.

---
## 5. TLS Handshake

When your browser (the **client**) connects to a secure website (the **server**), here’s what happens under the hood — broken down step by step using easy-to-follow key names.

### 5.1. Client Hello

> The browser begins the handshake.

- The client (browser) generates a temporary private key: `a`.
    
- It uses this to create a matching public key: `ag` (using a shared rule or method `g`).
    
- It sends:
    
    - `ag` (its public key)
        
    - A list of supported encryption methods
        
    - Its TLS version (e.g. TLS 1.3)
        

`a` never leaves the browser.


### 5.2. Server Hello

> The website responds.

- The server generates its own temporary private key: `b`.
    
- It uses this to create a public key: `bg` (same rule `g`).
    
- It sends:
    
    - `bg` (its public key)
        
    - Its digital certificate, which includes a public identity key used to prove it’s the real site (e.g., `google.com`)
        
    - Agreed settings for encryption
        

`b` stays on the server. 
The certificate helps the client trust the site’s identity.


### 5.3. Certificate Verification

> The browser checks the server’s identity based on the certificate it receives.

- The server sends its certificate along with any intermediates.
    
- The browser:
    
    - **Builds a chain of trust** from the server’s certificate up to a trusted root CA in the local trust store.
        
    - **Verifies signatures** along the chain.
        
    - **Checks the domain name** in the certificate matches the URL (e.g., `example.com`).
        
    - **Ensures validity**: the certificate isn’t expired or used before its start date.
        
    - **Checks revocation status** using OCSP or CRLs.
        
- If all checks pass, the connection proceeds and the lock icon appears in the browser.
    
- If any check fails, the browser blocks the site and shows a security warning.
    

### 5.4. Shared Secret Creation

> Both sides now build the same private shared key.

- **Client combines**: its own `a` with the server’s `bg` → gets `abg`
    
- **Server combines**: its own `b` with the client’s `ag` → also gets `abg`
    

Both sides now hold the same shared secret `abg`, without ever revealing `a` or `b`.

### 5.5. Key Derivation

> The shared secret turns into real encryption keys.

- `abg` is passed into a secure algorithm that produces:
    
    - A key to encrypt messages from the **client**
        
    - A key to encrypt messages from the **server**
        
- These are the **session keys** used for the rest of your connection.
    

### 5.6. Secure Session Begins

> Everything after this is encrypted.

- Both browser and server:
    
    - Encrypt their messages using the session keys
        
    - Ensure each message is also verified (not tampered with)
        
Once the handshake is complete, both `a` and `b` are securely erased, as required by the TLS 1.3 standard ([RFC 8446 §7.2](https://datatracker.ietf.org/doc/html/rfc8446#section-7.2)).

### The Big Idea: Forward Secrecy

**Forward secrecy** means: even if the server’s future keys are stolen, the past stays secret — because each session had its own keys that are gone forever.

---
### References
- [Transport Layer Security, TLS 1.2 and 1.3 Explained by Example - YouTube](https://www.youtube.com/watch?v=AlE5X1NlHgg&list=PLQnljOFTspQW4yHuqp_Opv853-G_wAiH-)
- [Secret Key Exchange (Diffie-Hellman) - Computerphile - YouTube](https://www.youtube.com/watch?v=NmM9HA2MQGI)
- [Diffie-Hellman Key Exchange: How to Share a Secret - YouTube](https://www.youtube.com/watch?v=85oMrKd8afY)