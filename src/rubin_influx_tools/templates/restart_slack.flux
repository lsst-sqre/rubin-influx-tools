import "slack"

option v = {bucket: "_monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}}}

default_cluster = "roundtable"

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
    |> map(
        fn:
            (r) =>
                ({r with slack_ret:
                        slack.message(
                            text: "Restart(s) for ${r.cluster}/${r.application}/${r.pod_name} (${r.container_name}) at ${r._time}: ${r._value}",
                            color: "danger",
                            channel: r.channel,
                            url: r.webhook_url,
                        ),
                }),
    )
    |> yield()
