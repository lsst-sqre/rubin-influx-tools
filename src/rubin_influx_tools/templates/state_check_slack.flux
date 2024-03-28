import "slack"
import "strings"

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
        if v == 0 then
             "good"
        else if v == 1 then
            "danger"
        else
            "warning"

    return color
}

from(bucket: "multiapp_")
    |> range(start: -5m)
    |> map(fn: (r) => ({r with channel: wh_rec(cluster: r.cluster).channel}))
    |> map(fn: (r) => ({r with webhook_url: wh_rec(cluster: r.cluster)._value}))
    |> filter(fn: (r) => r._measurement == "kubernetes_pod_container")
    |> filter(fn: (r) => r._field == "pod_state")
    |> group(columns: ["_measurement", "_field", "_value", "_time", "application", "alerted", "cluster", "container_name", "phase", "phase_reason", "pod_name", "readiness", "state", "state_code", "state_reason"])
    // Suppress cachemachine pulling messages, which is normal operation
    |> filter(fn: (r) => (not (r.application == "cachemachine" and strings.hasPrefix(v: r.pod_name, prefix: "jupyter-"))))
    // Also suppress moneypenny initcommission messages, since that too
    // takes a while when the provisioner actually has to do something.
    |> filter(fn: (r) => (not (r.application == "moneypenny" and r.container_name == "initcommission" and strings.hasSuffix(v: r.pod_name, suffix: "-pod"))))
    // Suppress if we have already seen this message
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
