# Credit Management

Reusable Frappe credit management platform for any consuming app.

## Integration

Consuming apps must use the stable public API:

```python
import credit_management.api as credit_api
```

Do not mutate balances or ledger rows directly.

## Documentation

- [Architecture](docs/architecture.md)
- [Public API](docs/public_api.md)
- [Decision Log](docs/decision_log.md)
- [v1.0 Migration Plan](patches/v1_0/README.md)

## Development status

| Gate | Status |
|---|---|
| 0 Discovery | Complete |
| 1 Architecture Scaffold | Complete |
| 1.5 Legacy MVP Cleanup | Complete |
| 2 Core Ledger | Pending |

## License

MIT