# Conversation behind 064166f2079a: Reject duplicate refunds and cap refunds per order

## User

Support agents keep double-clicking refund and we refund twice (see reports/refund-abuse.md). Limit refunds to 3 per order per hour and reject exact duplicates within a minute.

### Tool call: `shell`

```
{
 "command": [
  "bash",
  "-lc",
  "rg -n 'def create_refund' app"
 ]
}
```

### Tool result

```
app/refunds.py:5:def create_refund(order_id, amount, agent):
```

### Assistant (thinking)

Duplicates happen within seconds, same amount and agent. A per-order limit alone would still let the second click through, so check for an identical refund in the last 60s first, then the hourly cap. Count from the refunds table instead of an in-memory limiter: there are 4 API replicas.

### Tool call: `apply_patch`

```
*** Begin Patch
*** Update File: app/refunds.py
@@
-def create_refund(order_id, amount, agent):
-    order = db.orders.get(order_id)
+MAX_PER_HOUR = 3
+
+
+class RefundRejected(Exception):
+    pass
+
+
+def create_refund(order_id, amount, agent):
+    if db.refunds.count(order_id=order_id, amount=amount, since_seconds=60):
+        raise RefundRejected("duplicate refund within a minute")
+    if db.refunds.count(order_id=order_id, since_seconds=3600) >= MAX_PER_HOUR:
+        raise RefundRejected("refund limit reached for this order")
+    order = db.orders.get(order_id)
*** End Patch

```

### Tool result

```
Success. Updated app/refunds.py
```

### Tool call: `shell`

```
{
 "command": [
  "bash",
  "-lc",
  "pytest -q tests"
 ]
}
```

### Tool result

```
6 passed in 0.48s
```

## Assistant

Refunds now reject an identical refund within 60s and cap each order at 3 refunds per hour. Counts come from the refunds table, so the limit holds across all API replicas.
