---
title: "A Polling Cache You Can Swap for an Event Stream Later"
date: 2026-05-09
category: Engineering
type: blog
---

There's a particular kind of expensive read in any payments-shaped system. A user shows up at checkout, and to make a decision you need the answer to a question whose source of truth is spread across half a dozen tables — outstanding payments, processing payments, verification status, blocklist membership, fraud flags. Computing the answer live is correct but slow. Simply caching at query time means you pay the latency cost once still, which in latency sensitive applications can be too much. Without a distributed cache, caching at query time also means low hit rate - the user needs to hit the exact same pod twice. In my experience, the built in MySQL cache is not effective for this problem, either.

The fix that worked for me, three times in a row now in the same service, is a database-backed cache shared across all pods, kept fresh by a worker that polls a change source. Latency on the hot path went from 100–500ms to under 10ms. 

This is essentially the **transactional outbox** pattern, but not exactly. The version I keep building has a property I haven't seen written down explicitly: the consumer doesn't care where its change events come from. It can poll the source table directly, tail an outbox, or — eventually — subscribe to a Kafka topic, and the rest of the system doesn't change. That swap-ability turns out to be the whole point.

## The pieces

There are four moving parts. None of them are novel on their own.

1. **A read-side cache table.** A flat table, one row per entity, indexed on the entity's UUID. Each cached field has its own `*_updated_at` so you can manage them independently. This is just the **Materialized View** pattern.

2. **A change source.** Either the domain table itself (queried by `updated_at` window) or a dedicated `outbox_*` table written transactionally by the producer. The outbox is the **Transactional Outbox** pattern from Chris Richardson; the domain-table polling is the duct-tape version of it.

3. **A consumer cursor.** A tiny table — `(provider, consumer, last_read_id)` — that lets the worker resume where it left off and lets multiple consumers tail the same outbox at different speeds.

4. **A worker that pulls events, recomputes the affected fields, and writes them to the cache table.** This is the **Polling Publisher** from Richardson's catalog. The same worker has a `naive_full_refresh` mode for backfill and a `refresh_for_set_of_users` mode for support escalations, because every CDC-shaped system needs both of those eventually.

Optionally: a **Redis side-channel** that the producer writes to with a "user X had a change at time T" key. The hot path, before trusting the DB cache, checks Redis: if there's a newer invalidation than the cache's `updated_at`, fall through to the live calculation. This is the staleness fence — it costs you a Redis GET on the hot path but lets you tolerate seconds of cron lag without lying to the decision flow.

## The interface that lets you swap things

The consumer worker doesn't talk to `payment_statuses` directly. It talks to a small interface:

```go
type ChangeSource interface {
    GetEvents(ctx context.Context, afterCursor uint, limit int) ([]ChangeEvent, error)
}

type ChangeEvent struct {
    ID        uint      // monotonic, used as the cursor
    EntityID  uint      // user/account/whatever the cache is keyed on
    CreatedAt time.Time
}
```

You write three implementations and pick one at startup:

- **`PollDomainTable`** — `SELECT user_id FROM payment_statuses WHERE updated_at BETWEEN ? AND ?`. Easy to ship, no producer-side changes, fine at low volume. The cursor is a timestamp window, not an ID.

- **`PollOutbox`** — `SELECT * FROM outbox_payment_statuses WHERE id > ? ORDER BY id LIMIT ?`. The producer writes to the outbox in the same transaction as the domain change. Cursor is the autoincrement ID, persisted in `outbox_cursors`.

- **`SubscribeKafka`** — when you eventually have a Debezium connector or a service emitting events to Kafka, you write a third implementation. The cursor becomes the partition offset. The cache worker doesn't change.

The point isn't that the third one is hypothetical. It usually is. The point is that committing to the interface up front means "we'll move to events later" stops being a multi-quarter rewrite and becomes a swap of one struct for another. The first time you do this it feels like over-engineering. The second time, when someone asks "can we move this off polling?" and the answer is "yes, here, this afternoon," it stops feeling that way.

## Why the cursor goes in its own table

The cursor table is the smallest, most boring part of the system, and it's the one I've gotten wrong the most. Two rules I now follow:

1. **The cursor is `(provider, consumer, last_read_id)`, not just `last_read_id`.** Multiple consumers will tail the same outbox eventually — one writes the cache, another emits invalidations to Redis, a third ships events to a warehouse. Each one needs its own offset. If you key the cursor only by the outbox name you'll regret it within a year.

2. **Update the cursor _after_ you've successfully processed the batch, not as part of fetching it.** This makes the consumer at-least-once. You'll need to make the cache write idempotent anyway (it's an upsert keyed on entity ID, so this is free), but be deliberate about the order.

```go
events, err := source.GetEvents(ctx, cursor.LastReadID, batchSize)

// ... process events, write cache rows ...

cursor.LastReadID = events[len(events)-1].ID
cursorService.Upsert(cursor)
```

If the worker crashes between processing and the cursor update, you reprocess the batch on restart. That's fine — the cache write is idempotent. If you flip the order you'll silently drop events the day a deploy gets sigkill'd mid-batch, and you'll learn about it from a customer.

## What the worker actually does

Three job modes, one binary:

- **Incremental** (the primary one): runs continuously, pulls events since the last cursor, fans out to a worker pool, recomputes the cached fields per entity, writes back to the cache table only if a value actually changed. ~5 second poll interval. This is where the 95% hit rate comes from.

- **Full refresh** (maintenance): paginates through every user, recomputes everything. Slow, parallelized, resumable via offset. Used for backfills, for verifying the cache hasn't drifted, and for the first deploy.

- **Targeted** (on-demand): takes a list of user UUIDs and refreshes only those. Used by support: "this user is seeing a stale credit limit, can you nudge their cache?"

All three live in the same package and share the same `processEntity` function. The only difference is how they enumerate the entities to process. That sharing matters: the day someone changes how a cached field is computed, you don't want full refresh and incremental refresh disagreeing about it.

## The Redis staleness fence

The DB cache is eventually consistent. The cron is fast but it's not synchronous, and there are flows — the decisioning hot path is one — where reading a 4-second-stale value would be wrong.

The trick I borrowed from various cache-aside writeups: have the producer write a tiny invalidation marker to Redis as part of the change event, with a short TTL (10 minutes is plenty). On the read path, before trusting the DB cache, do a Redis GET on the entity's invalidation key:

- **No key, or older than the cache's `updated_at`** → trust the cache.

- **Key newer than `updated_at`** → fall through to the live calculation, and let the cron catch up.

This costs you one Redis GET on the hot path. It buys you the ability to tolerate the cron being a few seconds behind without serving wrong answers in the windows that actually matter. Critically, the invalidation writer can also be one of the consumers tailing the outbox — same interface, different sink. So when you swap the polling for Kafka, the invalidation path comes along for free.

## What this is not

A few things to be honest about:

- **It's not real-time.** The fence makes it correct under load, not instant. Sub-second latency on the cached read requires a different architecture.

- **It's not free of operational toil.** The cursor can stall, the outbox can grow, the worker can fall behind. You need metrics on cursor lag (newest event ID − cursor), worker throughput, and cache write rate, with alerts on each. None of those are hard, but you have to actually wire them up.

- **It's not a replacement for events.** It's a stepping stone. If you already have a healthy event stream, just subscribe to it. The pattern shines when you don't, and you want to ship something that won't have to be rewritten when you do.

## The thing I keep coming back to

I built this three times in the same service before I noticed I was building the same thing. The first time it was for a "is this user verified" check. The second time, for outstanding-payment sums on the credit-limit decision. The third time, for blocklist and fraud flag membership. Each one started as "we need to cache this" and ended up as the same four pieces — cache table, change source, cursor, worker — wearing slightly different clothes.

The reason it keeps working is that the abstraction is at the right altitude. Not "here is a generic caching framework" — those always overshoot — but "here is the shape your cache should take when the source of truth is in another table and you might want to switch to events later." That's narrow enough to be a copy-paste template and general enough to fit most decision-shaped reads.

If I had to compress the lesson into one sentence: **commit to the consumer interface, not the change source, and the polling-to-streaming migration stops being scary.**
