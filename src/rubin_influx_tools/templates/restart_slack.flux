import "slack"

option v = {bucket: "monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}}}

default_cluster = "roundtable"

needs_alert = (msg) => {
    record =
        from(bucket: "alerted_")
            |> range(start: -1h)
            |> filter(fn: (r) => r.message == msg)
            |> findRecord(idx:0, fn: (key) => key.message == msg )

    rv =
        if exists(record.message) then false else true
    return rv
}

wh_rec = (cluster) => {
    default_rec =
        from(bucket: "webhooks_")
            |> range(start: 0)
            |> filter(fn: (r) => r["_measurement"] == "webhook")
            |> findRecord(idx: 0, fn: (key) => key.cluster == default_cluster)

    record =
        from(bucket: "webhooks_")
            |> range(start: 0)
            |> filter(fn: (r) => r["_measurement"] == "webhook")
            |> findRecord(idx: 0, fn: (key) => key.cluster == cluster)

    rec = if exists record then record else default_rec

    return rec
}

from(bucket: "multiapp_")
    |> range(start: -5m)
    |> map(fn: (r) => ({r with channel: wh_rec(cluster: r.cluster).channel}))
    |> map(fn: (r) => ({r with webhook_url: wh_rec(cluster: r.cluster)._value}))
    |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
    |> filter(fn: (r) => r["_field"] == "differential_restarts")
    |> group(columns: ["_time"])
    |> filter(fn: (r) => r._value != 0)
    |> filter(fn: (r) => needs_alert(msg: r.message))
    |> map(
        fn:
            (r) =>
                ({r with slack_ret:
                        slack.message(
                            text: r.message,
                            color: "danger",
                            channel: r.channel,
                            url: r.webhook_url,
                        ),
                }),
    )
    |> to(bucket:"alerted_", org:"square")
    |> yield()
