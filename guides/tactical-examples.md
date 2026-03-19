# Tactical Examples

This guide shows **how** to implement common security practices step-by-step. Use these as templates when building your own features.

---

## How to Use This Guide

Each example follows the same pattern:

1. **The Problem** - What security gap we're addressing
2. **The Analogy** - A relatable mental model
3. **The Tactic** - Step-by-step implementation
4. **Verification** - How to confirm it's working

---

## Example 1: Adding API Key Rotation

### The Problem

Your service uses an API key to connect to an external service. If that key is compromised, you need to be able to rotate it without downtime.

### The Analogy

Think of this like changing the locks on your house. You want to:
- Have new keys ready before you change the lock
- Give the new keys to people who need them
- Change the lock
- Confirm the old keys no longer work

### The Tactic

**Step 1: Store secrets in a secret manager (not code)**

```python
# Bad - hardcoded in code
API_KEY = "example-hardcoded-key"

# Good - pulled from secret manager at runtime
import boto3

def get_api_key():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='my-service/api-key')
    return response['SecretString']
```

**Step 2: Support multiple valid keys during rotation**

```python
# In your config, support a list of valid keys
VALID_API_KEYS = get_api_keys()  # Returns list from secret manager

def validate_api_key(provided_key):
    return provided_key in VALID_API_KEYS
```

**Step 3: Create a rotation runbook**

```markdown
## API Key Rotation Runbook

1. Generate new key in external service dashboard
2. Add new key to secret manager (keep old key)
3. Deploy/restart services to pick up new key
4. Verify new key works: `curl -H "Authorization: Bearer $NEW_KEY" /health`
5. Revoke old key in external service dashboard
6. Remove old key from secret manager
```

### Verification

- [ ] Secret is not in source code (grep for it)
- [ ] Service can be restarted and still authenticate
- [ ] Rotation runbook has been tested in staging

---

## Example 2: Implementing Data Isolation

### The Problem

You have a multi-tenant application where Customer A should never see Customer B's data.

### The Analogy

Think of apartment buildings. Every tenant lives in the same building, but:
- Each apartment has its own lock
- The mail carrier sorts mail by apartment number
- You can't accidentally walk into someone else's unit

### The Tactic

**Step 1: Include tenant context in every query**

```python
# Bad - no tenant filter
def get_user_data(user_id):
    return db.query("SELECT * FROM users WHERE id = ?", user_id)

# Good - tenant filter enforced
def get_user_data(user_id, tenant_id):
    return db.query(
        "SELECT * FROM users WHERE id = ? AND tenant_id = ?",
        user_id,
        tenant_id
    )
```

**Step 2: Extract tenant from authentication context**

```python
# Get tenant from the authenticated session, not from user input
def get_current_tenant():
    # Tenant comes from verified JWT, not request params
    return g.current_user.tenant_id

@app.route('/api/users/<user_id>')
@require_auth
def get_user(user_id):
    tenant_id = get_current_tenant()  # From auth, not request
    return get_user_data(user_id, tenant_id)
```

**Step 3: Add tests that verify isolation**

```python
def test_tenant_isolation():
    # Create users in different tenants
    user_a = create_user(tenant_id="tenant-a")
    user_b = create_user(tenant_id="tenant-b")

    # Authenticate as tenant A
    client = authenticate_as(tenant="tenant-a")

    # Should get tenant A's user
    response = client.get(f"/api/users/{user_a.id}")
    assert response.status_code == 200

    # Should NOT get tenant B's user
    response = client.get(f"/api/users/{user_b.id}")
    assert response.status_code == 404  # Not 403 - don't reveal existence
```

### Verification

- [ ] Every database query includes tenant filter
- [ ] Tenant ID comes from auth context, never user input
- [ ] Tests exist that verify cross-tenant access fails

---

## Example 3: Adding Audit Logging

### The Problem

You need to track who did what in your system for security investigations and compliance.

### The Analogy

Think of security cameras in a building:
- They record continuously (not just when something bad happens)
- Footage is stored somewhere you can't tamper with
- You can review footage to see who was where and when

### The Tactic

**Step 1: Define what to log**

```python
# Log structure for security-relevant events
audit_log = {
    "timestamp": "2026-01-30T10:15:00Z",
    "actor": {
        "user_id": "user-123",
        "email": "alice@company.com",
        "ip_address": "192.168.1.1"
    },
    "action": "user.permission.granted",
    "resource": {
        "type": "dashboard",
        "id": "dashboard-456"
    },
    "details": {
        "permission": "edit",
        "granted_by": "admin-789"
    },
    "outcome": "success"
}
```

**Step 2: Create a logging helper**

```python
import structlog

audit_logger = structlog.get_logger("audit")

def log_audit_event(actor, action, resource, details, outcome="success"):
    audit_logger.info(
        action,
        actor_id=actor.id,
        actor_email=actor.email,
        actor_ip=get_client_ip(),
        resource_type=resource.type,
        resource_id=resource.id,
        details=details,
        outcome=outcome
    )
```

**Step 3: Log at key decision points**

```python
@app.route('/api/dashboards/<id>/permissions', methods=['POST'])
@require_auth
def grant_permission(id):
    dashboard = get_dashboard(id)

    # Check authorization
    if not current_user.can_manage(dashboard):
        log_audit_event(
            actor=current_user,
            action="dashboard.permission.grant_attempt",
            resource=dashboard,
            details={"reason": "insufficient_privileges"},
            outcome="denied"
        )
        return {"error": "Forbidden"}, 403

    # Perform action
    grant_access(dashboard, request.json['user_id'], request.json['level'])

    log_audit_event(
        actor=current_user,
        action="dashboard.permission.granted",
        resource=dashboard,
        details={
            "granted_to": request.json['user_id'],
            "level": request.json['level']
        },
        outcome="success"
    )

    return {"status": "ok"}
```

### Verification

- [ ] Logs are written to immutable storage (not local files)
- [ ] Sensitive data (passwords, tokens) is NOT logged
- [ ] You can answer "who accessed X in the last 24 hours?"

---

## Example 4: Input Validation

### The Problem

User input can contain malicious data that exploits your system.

### The Analogy

Think of TSA screening at airports:
- Everything gets inspected before entering
- Suspicious items are rejected, not "fixed"
- The check happens at the perimeter, not inside the plane

### The Tactic

**Step 1: Validate at the boundary**

```python
from pydantic import BaseModel, validator, constr

class CreateUserRequest(BaseModel):
    email: constr(max_length=255)
    name: constr(max_length=100, min_length=1)
    role: str

    @validator('email')
    def validate_email(cls, v):
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError('Invalid email format')
        return v.lower()

    @validator('role')
    def validate_role(cls, v):
        allowed_roles = ['viewer', 'editor', 'admin']
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {allowed_roles}')
        return v

@app.route('/api/users', methods=['POST'])
def create_user():
    # Validation happens here - invalid data never reaches business logic
    try:
        data = CreateUserRequest(**request.json)
    except ValidationError as e:
        return {"error": e.errors()}, 400

    # Now data is guaranteed to be valid
    return user_service.create(data)
```

**Step 2: Reject, don't sanitize**

```python
# Bad - trying to "fix" bad input
def sanitize_input(value):
    return value.replace('<script>', '')  # Attackers will bypass this

# Good - reject bad input entirely
def validate_input(value):
    if '<' in value or '>' in value:
        raise ValueError("Invalid characters in input")
    return value
```

**Step 3: Use parameterized queries**

```python
# Bad - string concatenation allows SQL injection
def find_user(email):
    query = f"SELECT * FROM users WHERE email = '{email}'"
    return db.execute(query)

# Good - parameterized query
def find_user(email):
    return db.execute(
        "SELECT * FROM users WHERE email = ?",
        [email]
    )
```

### Verification

- [ ] All API endpoints validate input with a schema
- [ ] No string concatenation in SQL queries
- [ ] Validation errors return 400, not 500

---

## Adding Your Own Examples

When documenting a new tactic, follow this template:

```markdown
## Example N: [Tactic Name]

### The Problem
[1-2 sentences describing the security gap]

### The Analogy
[Relatable comparison that non-engineers can understand]

### The Tactic
[Step-by-step implementation with code examples]

### Verification
[Checklist to confirm correct implementation]
```

---

## Related Resources

- [Quick Security Review](quick-security-review.md) - The 10 essential questions
- [Self-Service Security Checklist](self-service-checklist.md) - Validation checklist
- [Claude Prompting Guide](claude-prompting-guide.md) - Using AI for documentation
