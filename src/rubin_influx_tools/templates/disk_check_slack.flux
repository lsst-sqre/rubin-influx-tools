import "slack"

option v = {bucket: "monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}}}

default_cluster = "roundtable.lsst.cloud"

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

colorLevel = (v) => {
    color =
        if float(v: v) > 95.0 then
            "danger"
        else if float(v: v) >= 85.0 then
            "warning"
        else
            "good"

    return color
}

from(bucket: "monitoring")
    |> range(start: -2m)
    |> map(fn: (r) => ({r with channel: wh_rec(cluster: r.cluster).channel}))
    |> map(fn: (r) => ({r with webhook_url: wh_rec(cluster: r.cluster)._value}))
    |> filter(fn: (r) => r["_measurement"] == "disk")
    |> filter(fn: (r) => r["_field"] == "used_percent")
    |> group(columns: ["_time"])
    |> filter(fn: (r) => r._value > 85.0)
    |> map(fn: (r) => ({ r with message: "${r.host}: ${r.path} at ${r._value}% used" }))
    |> filter(fn: (r) => needs_alert(msg: r.message))
    |> map(
        fn:
            (r) =>
                ({r with slack_ret:
                        slack.message(
                            text: r.message,
                            color: colorLevel(v: r._value),
                            channel: r.channel,
                            url: r.webhook_url,
                        ),
                }),
    )
    |> to(bucket: "alerted_", org: "square")
    |> yield()
