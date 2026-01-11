### Purpose
Encryption is used to protect the confidentiality of data by converting it into an unreadable format. Unlike hashing, encryption is reversible, provided the correct key is available.
### Types of Encryption
#### 1. Symmetric Encryption
- **Description:** Uses the same key for both encryption and decryption. It is generally faster and more efficient than asymmetric encryption but requires secure key distribution.
- **Example Algorithm:** AES (Advanced Encryption Standard).
- **Use Cases:** Encrypting data at rest, such as files or databases, where the same key is used for both encryption and decryption.
#### Historical Example: The Caesar Cipher
- **Caesar Cipher:** One of the earliest known encryption techniques, named after Julius Caesar. It is a simple substitution cipher where each letter in the plaintext is shifted by a fixed number of positions in the alphabet.
  - **Example:** With a shift of 3, A becomes D, B becomes E, etc.
  - **Plaintext:** HELLO
  - **Ciphertext (Shift 3):** KHOOR
- **Limitations:** The Caesar Cipher is easily broken, especially with modern computational methods. It is vulnerable to frequency analysis, where an attacker can deduce the original letters based on their frequency in the ciphertext.
#### 2. Asymmetric Encryption
- **Description:** Uses a pair of keys, one public and one private. Data encrypted with the public key can only be decrypted with the corresponding private key.
- **Example Algorithm:** RSA (Rivest-Shamir-Adleman).
- **Use Cases:** Secure communications, such as in HTTPS and SSH, where the public key is widely distributed, and only the holder of the private key can decrypt the data.
### Asymmetric Encryption and SSH
#### How SSH Works
- **Key Pair Generation:** SSH uses asymmetric encryption to secure remote connections. Users generate a key pair consisting of a public key and a private key.
- **Public Key Distribution:** The public key is stored on the remote server, while the private key remains secure on the user's local machine.
- **Authentication:** Upon connecting to the server, the user's private key generates a digital signature. The server verifies this signature using the public key, ensuring the user's authenticity.
- **Session Encryption:** After authentication, SSH employs symmetric encryption for the session, with the symmetric key securely exchanged using asymmetric encryption.
#### Security Benefits
- **No Passwords Required:** SSH key pairs eliminate the need for passwords, reducing the risk of password-based attacks.
- **Protection Against Man-in-the-Middle Attacks:** The integrity of the public key system helps prevent attackers from intercepting communications.
### Modern Asymmetric Encryption

#### 1. RSA (Rivest-Shamir-Adleman)
- **Description:** A widely used asymmetric encryption algorithm based on the mathematical properties of large prime numbers.
- **Use Cases:** Digital signatures, SSL/TLS, secure email (PGP/GPG).
#### 2. Elliptic Curve Cryptography (ECC)
- **Description:** A newer form of asymmetric encryption offering similar security to RSA but with shorter key lengths, making it more efficient.
- **Use Cases:** Mobile devices, cryptocurrencies, secure communications.
### Example Command for SSH Key Generation
```bash
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
```

---

Additional Resource

To create a free SSL certificate for your website, you can use [Certbot](https://certbot.eff.org/), which provides an easy way to set up SSL/TLS certificates using Let's Encrypt.