# Conductor

Conductor is the consensus engine for the Chorus ecosystem. It provides a high-throughput, byzantine fault-tolerant (BFT) ordering service for transactions, which is essential for the security and consistency of the federated network.

## Purpose

In a decentralized system like Chorus, there needs to be a way for all participants to agree on the order of events without trusting a central party. Conductor solves this problem by implementing a BFT consensus algorithm, as detailed in CFP-010.

## How it Works

- **Transaction Ordering:** Conductor takes transactions from Chorus Bridge instances and orders them into a canonical, immutable sequence.
- **Validation:** It ensures that all transactions are valid and that no malicious actor can tamper with the history of events.
- **Fault Tolerance:** Conductor is designed to be resilient to failures and malicious attacks, ensuring the continuous operation of the Chorus network.
- **Timestamp-Free Operation:** Conductor operates without relying on timestamps, further enhancing its resistance to certain types of attacks and ensuring fairness. For more details, refer to the .cfp/ files, specifically CFP-011.

## Role in Anonymity

While Conductor's primary role is to provide consensus, it is also designed to support the anonymity goals of the Chorus ecosystem. By providing a secure and decentralized ordering service, it eliminates the need for a central authority that could otherwise become a point of failure or a target for surveillance.