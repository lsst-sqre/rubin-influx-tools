import "slack"
import "influxdata/influxdb/secrets"

option v = {bucket: "_monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}}}

slackurl = secrets.get(key: "slack_notify_url")
toSlack = slack.endpoint(url: slackurl)

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
    |> range(start: -2m)
    |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
    |> filter(fn: (r) => r["_field"] == "state_code")
    |> group(columns: ["_time"])
    |> filter(fn: (r) => r._value != 0)
    |> toSlack(
        mapFn: (r) =>
            ({
                channel: "roundtable-test-notifications",
                text: "${r.cluster}/${r.container_name}/${r.pod_name} at ${r._time}: state ${r.state} (${r.state_reason}), phase ${r.phase} (${r.phase_reason}), readiness ${r.readiness}",
                color: colorLevel(v: r._value),
            }),
    )()
    |> yield()
