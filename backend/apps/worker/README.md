# vld-worker

Relays the transactional outbox to RabbitMQ and sends the letters.

```bash
uv run vld-worker
```

Needs `BROKER_URL` (`amqp://user:password@host:5672/vhost`) besides the settings
of the API (`DATABASE_URL`, `REDIS_*`, `JWT_SECRET_KEY`, `EMAIL_*`, `APP_ENV`).

## How a letter travels

1. A use case writes an event to `auth.outbox` in its own transaction.
2. The relay claims a batch (`pending → sending`, `FOR UPDATE SKIP LOCKED`),
   publishes one task per row to RabbitMQ and marks the row `sent`.
3. The task runs the handler of the event: `prepare` stores the token and commits,
   `deliver` sends the letter. A bounce (5xx about the letter) is dropped; any
   other failure is retried by the broker (60, 120, 360 seconds, then every ten
   minutes, ten times).
4. A row that cannot be published is deferred with a backoff (10 seconds doubling
   up to 30 minutes) and fails after ten attempts. Rows of a worker that died in
   `sending` are released after 15 minutes.

Exchange `validate`, queues `validate.worker`, `validate.worker.delay` and
`validate.dead_letter`: named after the project, so a neighbour on the same
RabbitMQ is not disturbed.
