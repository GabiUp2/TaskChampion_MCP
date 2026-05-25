# Sample Taxonomy for Testing
**Schema version:** 1.0.0

---

## 1. Project Namespace

Projects use dot-notation hierarchies. Always lowercase. Maximum depth: 4 levels.

---

## 2. UDA Reference

### 2.1 `scope` — personal | work
**Required on all tasks.** Top-level discriminator. Use in filters to isolate domains.

```bash
task scope:work
```

### 2.2 `client` — free string
Work tasks only. Names the client or org. Examples: `acme`, `globex`.

### 2.3 `area` — infra | dev | learning | ops | data | security | tooling | career
Functional domain for cross-project clustering.

| Value | Meaning |
|---|---|
| `infra` | Infrastructure and servers |
| `dev` | Software development |
| `learning` | Courses and reading |
| `ops` | Operations and CI/CD |
| `data` | Data pipelines |
| `security` | Security hardening |
| `tooling` | Developer tooling |
| `career` | Career development |

### 2.4 `phase` — idea | research | design | testing | impl | validate | blocked
**Every task should have a phase.** The most important UDA for situational awareness.

| Value | Meaning |
|---|---|
| `idea` | Captured but unevaluated |
| `research` | Actively gathering info |
| `design` | Translating research into plans |
| `testing` | Running experiments |
| `impl` | Committed direction, executing |
| `validate` | Needs validation |
| `blocked` | Cannot proceed |

### 2.5 `hypothesis` — free string
Required when `phase` is 'research' or `phase` is 'testing'. State the question being investigated.

### 2.6 `versus` — free string
Required when `phase` is 'testing'. Names the options under comparison.

### 2.7 `effort` — XS | S | M | L | XL
T-shirt size estimate.

### 2.8 `confidence` — H | M | L
How well-defined this task is.

---

## 3. Tags

Tags capture cross-cutting concerns.

### Technology tags
`+linux`, `+python`, `+docker`

### Operational tags
| Tag | Meaning |
|---|---|
| `+next` | Current focus |
| `+waiting` | Blocked on someone |

---

## 8. Maintenance

- **When promoting a task from `idea` → `research`:** Add `hypothesis` describing what to investigate.
- **When promoting from `research` → `testing`:** Add `versus` naming the options.
- **When promoting from `testing` → `impl`:** Commit to a direction.

---

*Test fixture for schema_gen tests.*
