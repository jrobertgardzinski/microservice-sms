# microservice-sms

An SMS notification channel for the paddock — a sibling of `microservice-email` and
`microservice-push`. Framework-free Python (stdlib only), the uniform channel contract:

```
POST /send   {"to": "+48555123456", "subject": "...", "body": "..."}  -> 202 {"status":"SENT"}
GET  /health                                                          -> 200 {"status":"UP"}
```

By default it **stub-sends**: it validates the recipient (E.164) and message, logs, and returns a
deterministic id — so the whole stack runs with no telephony account. Set `SMS_PROVIDER` (and the
gateway's credentials) to send for real; the wire contract never changes.

```bash
python3 server.py                 # :8088, stub provider
python3 -m unittest test_server
```
