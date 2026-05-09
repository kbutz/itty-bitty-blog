---
title: "A Polling Cache You Can Swap for an Event Stream Later"
date: 2026-05-09
category: Engineering
tags: [caching, transactional-outbox, materialized-view, go, architecture]
type: blog
---

There's a particular kind of expensive read in any payments-shaped system. A user shows up at checkout, and to make a decision you need an answer whose source of truth is spread across half a dozen tables: outstanding payments, processing payments, verification status, blocklist membership, fraud flags. In a classic MySQL backed system, one that has no events system or is in the process of migrating to event based architecture, computing the answer live is correct but slow. Caching at query time means you still pay the full cost on the first hit, which is enough to disqualify it for latency-sensitive paths. Without a distributed cache, query-time caching also has a low hit rate - the same user has to land on the same pod twice. The built-in MySQL query cache hasn't been effective for this shape of problem either, in my experience.

What worked for me, three times in a row in the same service, is a database-backed cache shared across all pods, kept fresh by a worker that polls a change source. Latency on the hot path went from 100–500ms to under 10ms.

This is essentially the **transactional outbox** pattern, but not exactly. The version I keep building has a property I haven't seen written down explicitly: the consumer doesn't care where its change events come from. It can poll the source table directly, tail an outbox, or eventually subscribe to a Kafka topic, and the rest of the system doesn't change. That swap-ability turns out to be the whole point.

## The pieces

There are four moving parts. None of them are novel on their own.

1. **A read-side cache table.** A flat table, one row per entity, indexed on the entity's UUID. Each cached field has its own `*_updated_at` so you can manage them independently. This is just the **Materialized View** pattern.

2. **A change source.** Either the domain table itself (queried by `updated_at` window) or a dedicated `outbox_*` table written transactionally by the producer. The outbox is the **Transactional Outbox** pattern from Chris Richardson; the domain-table polling is the duct-tape version of it.

3. **A consumer cursor.** A tiny table - `(provider, consumer, last_read_id)` - that lets the worker resume where it left off and lets multiple consumers tail the same outbox at different speeds.

4. **A worker that pulls events, recomputes the affected fields, and writes them to the cache table.** This is the **Polling Publisher** from Richardson's catalog. The same worker has a `naive_full_refresh` mode for backfill and a `refresh_for_set_of_users` mode for support escalations. Every CDC-shaped system needs both eventually.

Optionally: a **Redis side-channel** that the producer writes to with a "user X had a change at time T" key. Before trusting the DB cache, the hot path checks Redis. If there's a newer invalidation than the cache's `updated_at`, it falls through to the live calculation. This is the staleness fence. It costs you a Redis GET on the hot path but lets you tolerate seconds of cron lag without lying to the decision flow.

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

- **`PollDomainTable`** - `SELECT user_id FROM payment_statuses WHERE updated_at BETWEEN ? AND ?`. Easy to ship, no producer-side changes, fine at low volume. The cursor is a timestamp window, not an ID.

- **`PollOutbox`** - `SELECT * FROM outbox_payment_statuses WHERE id > ? ORDER BY id LIMIT ?`. The producer writes to the outbox in the same transaction as the domain change. Cursor is the autoincrement ID, persisted in `outbox_cursors`.

- **`SubscribeKafka`** - once you have a Debezium connector or a service emitting events to Kafka, you write a third implementation. The cursor becomes the partition offset. The cache worker doesn't change.

The third one is usually hypothetical at first. That's fine. The point of committing to the interface up front is that "we'll move to events later" stops being a multi-quarter rewrite and becomes a swap of one struct for another. The first time you do this it feels like over-engineering. The second time, when someone asks "can we move this off polling?" and the answer is "yes, here, this afternoon," it stops feeling that way.

## Why the cursor goes in its own table

The cursor table is the smallest, most boring part of the system, and it's the one I've gotten wrong the most. Two rules I now follow:

1. **The cursor is `(provider, consumer, last_read_id)`, not just `last_read_id`.** Multiple consumers will eventually tail the same outbox - one writes the cache, another emits invalidations to Redis, a third ships events to a warehouse. Each one needs its own offset. Keying the cursor only by the outbox name forces a painful migration the day a second consumer shows up.

2. **Update the cursor _after_ you've successfully processed the batch, not as part of fetching it.** This makes the consumer at-least-once. You need the cache write to be idempotent anyway - it's an upsert keyed on entity ID, so this is free - but be deliberate about the order.

```go
events, err := source.GetEvents(ctx, cursor.LastReadID, batchSize)

// ... process events, write cache rows ...

cursor.LastReadID = events[len(events)-1].ID
cursorService.Upsert(cursor)
```

If the worker crashes between processing and the cursor update, you reprocess the batch on restart. That's fine - the cache write is idempotent. Flip the order and you silently drop events the day a deploy gets sigkill'd mid-batch, and you learn about it from a customer.

## What the worker actually does

Three job modes, one binary:

- **Incremental** (the primary one): runs continuously, pulls events since the last cursor, fans out to a worker pool, recomputes the cached fields per entity, writes back to the cache table only if a value actually changed. ~5 second poll interval. This is where the 95% hit rate comes from.

- **Full refresh** (maintenance): paginates through every user, recomputes everything. Slow, parallelized, resumable via offset. Used for backfills, for verifying the cache hasn't drifted, and for the first deploy.

- **Targeted** (on-demand): takes a list of user UUIDs and refreshes only those. Used by support: "this user is seeing a stale credit limit, can you nudge their cache?"

All three live in the same package and share the same `processEntity` function. The only difference is how they enumerate the entities to process. That sharing matters. When someone changes how a cached field is computed, you don't want full refresh and incremental refresh disagreeing about it.

## The Redis staleness fence

The DB cache is eventually consistent. The cron is fast but not synchronous, and some flows - the decisioning hot path is one - can't tolerate a 4-second-stale value.

The trick I borrowed from various cache-aside writeups: have the producer write a tiny invalidation marker to Redis as part of the change event, with a short TTL (10 minutes is plenty). On the read path, before trusting the DB cache, do a Redis GET on the entity's invalidation key:

- **No key, or older than the cache's `updated_at`** → trust the cache.
- **Key newer than `updated_at`** → fall through to the live calculation, and let the cron catch up.

This costs you one Redis GET on the hot path. It buys you the ability to tolerate the cron being a few seconds behind without serving wrong answers in the windows that actually matter. The invalidation writer can also be one of the consumers tailing the outbox - same interface, different sink. So when you swap the polling for Kafka, the invalidation path comes along for free.

## How to launch this safely

The four pieces above describe the steady state. Getting there - moving a hot read off a live query and onto a cache that some cron is keeping fresh - is the part where you can quietly start serving wrong answers to production traffic. The first time I did this, I underestimated this phase. The next two times, I built the same three safety mechanisms before I let any real traffic touch the cache.

Treat them as a set. Each one only works because the other two are there.

### 1. A flagged fallback to the live query

Wrap every cache read in a feature flag whose default is "use the live query." Roll the flag forward by user-id bucket - 1%, 10%, 50%, 100% - and keep the flag in place long after launch.

The point of the flag isn't to validate the cache. It's to give yourself a single switch to flip when the cron stalls, when the cursor gets corrupted, when someone ships a bug in the recompute logic, or when the underlying domain semantics change in a way you didn't account for. You want to be able to stop trusting the cache without a deploy.

A few rules I follow:

- **The flag gates the _read_, not the cron.** Keep the cron writing the cache even at 0% rollout. That way, when you flip to 1%, the cache is already warm and you're testing the read path, not the warm-up path.
- **Default to live on error.** If the cache lookup itself errors - connection blip, malformed row, missing entity - the read should silently fall through to the live query and emit a metric. Never return an error from the cache layer to the caller. The cache is an optimization, not a dependency.
- **Don't remove the fallback after launch.** The cost of leaving it in is one branch and one feature-flag check. The cost of ripping it out the week before a regression ships is much higher.

### 2. Live sampling against the live query

A cache that returns wrong answers but never errors is the failure mode you have to worry about. The cron can be running, the cursor can be advancing, the metrics can all look green, and the cache can still be silently drifting because the recompute logic disagrees with the live query in some edge case nobody thought to test.

The only defense is to keep computing the live answer for some fraction of reads, compare it to the cached answer, and alert when they disagree:

```go
if rand.Float64() < cacheComparisonSampleRate {
    go func() {
        live := computeLive(ctx, entityID)
        cached := readFromCache(ctx, entityID)
        if live != cached {
            metrics.CacheMismatch.WithLabelValues(field, "drift").Inc()
            log.Warn("cache drift detected",
                zap.Uint("entity_id", entityID),
                zap.Any("live", live),
                zap.Any("cached", cached),
            )
        }
    }()
}
```

A few things I've learned the hard way:

- **Sample rate is a knob, not a constant.** Start at 100% during the first week of any rollout. Every read runs live too, and you compare them all. Dial down to 10%, then 1%, once you've gone a week without finding a mismatch. Keep it _at_ 1% forever; never go to zero. The mismatches you discover a year later all come from that 1%. There may also be paths where it makes sense to keep 100% sampling rate at all times - these would be your most critical paths, like processing a live checkout or card authorization.
- **Run the comparison async, off the hot path.** The whole point of the cache is latency. If the comparison adds 50ms because you compute the live answer in-line, you've defeated the purpose. Spawn a goroutine, let it finish whenever, emit metrics from there.
- **Alert on mismatch _rate_, not mismatch count.** A single mismatch per million reads is noise, usually a race between the cron and the read. A 0.5% mismatch rate sustained over an hour is a real bug. Wire the alert to a ratio, with a floor so you don't page at low traffic.
- **Tag the metric with the field name.** When the alert fires, you want to know it's `outstanding_payments` drifting and not `verification_status`. They have different recompute logic and different owners.

### 3. Forced corrections at sample time

When the sampled comparison finds a mismatch, the worst thing you can do is just log it. The next request for that user reads the same wrong cache value. Whatever broke the cache for this user keeps producing the wrong answer until the cron happens to pick them up.

So at the moment of mismatch, force a refresh of that single entity:

```go
if live != cached {
    metrics.CacheMismatch.Inc()
    log.Warn("cache drift detected", ...)
    // Don't wait for the cron. Fix this row now.
    if err := cache.RefreshEntity(ctx, entityID); err != nil {
        log.Error("forced refresh failed", zap.Error(err))
    }
}
```

This is the same `refresh_for_set_of_users` mode the worker already exposes for support escalations, called with a one-element list. You're not building anything new. You're connecting two pieces you already have.

The forced correction does three things at once:

- **It self-heals the row.** The very next read for that user is correct, regardless of cron lag.
- **It bounds the blast radius of any drift bug.** If your recompute logic has a subtle bug that produces the wrong answer for 0.1% of users, the sampled comparison hits each affected user eventually, and each hit fixes them. You converge on correctness instead of accumulating staleness.
- **It validates the refresh path.** The targeted refresh is the same code path support uses to fix individual users. Exercising it on every drift event means you find out it's broken minutes after a deploy, not three weeks later when an angry customer surfaces.

One caveat: if the drift is caused by the recompute logic itself being wrong, the forced refresh writes the same wrong answer back. The sampling catches it again on the next request, and you see a sustained mismatch rate. That's the signal that you have a logic bug, not a freshness bug, and the flagged fallback is what you reach for.

### Why all three together

The three mechanisms compose into a launch posture where the cache can't silently lie to you for long:

- The flag lets you turn off the cache instantly if anything's wrong.
- The sampling lets you _know_ something's wrong, not just suspect it.
- The forced correction prevents known-wrong answers from being served twice.

Skip the flag and you have to deploy to recover. Skip the sampling and you don't know there's a problem until it shows up in support tickets. Skip the forced correction and your drift metric keeps firing for the same users for hours.

## The End

I built this three times for different use cases within the same domain. The cache strategy has been resilient and battle tested. The longest running version of this cache has now been live for close to two years at the time of writing this. In that time, there has been no major incidents or issues caused by the cache directly. Even during database outages or pod failures, the strategy behind the cache has resulted in a self healing zero downtime cache.

Honestly, the success of this strategy has been a surprise. I felt like I was over engineering the fallback & failover mechanisms because I had a root assumption that the cache would not work, or that it would be incident prone. The whole strategy felt like a hack when I first designed it, but I've proven myself wrong on that.
