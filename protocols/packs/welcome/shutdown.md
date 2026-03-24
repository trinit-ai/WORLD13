# WELCOME — Shutdown

---

If the user exits Welcome before completion, save whatever profile data has been captured so far. Don't lose progress.

> "No problem. Your profile's saved with what we've got so far. You can finish setting up anytime from the dropdown menu. Your packs are in Browse Packs when you're ready."

```
[STATE:welcome_interrupted=true]
[NAVIGATE:/]
```

On next login, if profile is still incomplete, Welcome reactivates — but picks up where they left off, not from scratch. Check which fields are populated and only ask for what's missing.
