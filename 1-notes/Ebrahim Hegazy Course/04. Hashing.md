### Purpose
Hashing is a process that converts data into a fixed-size string of characters, typically known as a hash or digest. It is primarily used to verify data integrity. Hashing is a one-way function, meaning it is irreversible; once data is hashed, it cannot be decoded back to its original form.
### Common Algorithms
- **SHA-256**
- **MD5**
- **SHA-1**
### Use Cases
- **Password Storage:** Hashing passwords before storage ensures that even if a database is compromised, the actual passwords remain hidden.
- **Data Integrity Checks:** Hashing is used in file verification processes to confirm that data has not been altered or tampered with.
### Security Considerations
- **Collisions:** A collision occurs when two different inputs produce the same hash value. Strong hash functions like SHA-256 are designed to minimize the likelihood of collisions.
- **Salting:** Adding random data (salt) to the input before hashing can thwart attackers from using precomputed tables (rainbow tables) to reverse-engineer the original data.
### Salt in Hashing
#### What is Salt?
A salt is a random value added to the input of a hash function before hashing. This makes each hash unique, even when the same input is hashed multiple times.
#### Why Use Salt?
- **Preventing Rainbow Table Attacks:** Salting ensures that even common passwords generate unique hashes, rendering precomputed tables ineffective.
- **Enhancing Security:** By introducing randomness, salting significantly reduces the risk of attacks based on predictable input patterns.
#### Example of Salting and Hashing
```bash
echo -n "unique_salt123your_password" | sha256sum
```
In this example, `unique_salt123` is the salt added to the password `your_password` before hashing with SHA-256. The resulting hash will be unique, even if `your_password` is the same across different systems or users.
### Additional Considerations
- **Peppering:** In addition to salting, peppering involves adding a secret key (known as a pepper) to the data before hashing. Unlike salt, which is unique for each user, the pepper is consistent across all hashed data, adding an extra layer of security.