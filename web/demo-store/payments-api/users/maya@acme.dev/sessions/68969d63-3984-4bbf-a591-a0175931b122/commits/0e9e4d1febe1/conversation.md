# Conversation behind 0e9e4d1febe1: Add unique constraints for webhook events and captures

### Tool result

```
[main fa76cc9] Make payment webhook idempotent
```

## User

Also make this impossible at the database level, in case someone adds another code path.

### Tool call: `Write`

```
{
 "file_path": "/home/dev/code/payments-api/migrations/0007_processed_events.sql",
 "content": "CREATE TABLE processed_events (\n    event_id text PRIMARY KEY,\n    processed_at timestamptz NOT NULL DEFAULT now()\n);\n\n-- one successful capture per order, whatever calls it\nCREATE UNIQUE INDEX captures_one_per_order ON captures (order_id) WHERE status = 'succeeded';\n"
}
```

### Tool result

```
File created successfully at: migrations/0007_processed_events.sql
```

## Assistant

Added migration 0007: `processed_events` keyed by event id, and a partial unique index so an order can only ever have one succeeded capture.

### Tool call: `Bash`

```
{
 "command": "git commit -am \"Add unique constraints for webhook events and captures\"",
 "description": "Commit"
}
```
