### Frappe Playbook

Provider-Agnostic Playbook Architecture

### Event Payload Structure

When Frappe Playbook triggers an external provider (or a native playbook execution), it passes the target document as a direct, unwrapped JSON payload.

For example, when a `ToDo` document is created, the resulting event payload will be:
```json
{
  "name": "e5f2a1b9",
  "doctype": "ToDo",
  "description": "Fix the bug in the login flow",
  "status": "Open",
  "owner": "user@example.com",
  "creation": "2024-05-23 10:00:00",
  "...": "..."
}
```

*Note: In versions prior to `1.x.x`, this payload was wrapped in a `"doc"` object (e.g. `{"doc": {"name": "e5f2a1b9"}}`). It is now fully unwrapped for better compatibility with external webhook systems and flat integrations.*

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench install-app frappe_playbook
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/frappe_playbook
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
