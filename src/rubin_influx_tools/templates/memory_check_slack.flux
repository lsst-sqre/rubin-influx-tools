import "slack"
import "influxdata/influxdb/secrets"

option v = {bucket: "_monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}}}

slackurl = secrets.get(key: "slack_notify_url")
toSlack = slack.endpoint(url: slackurl)

colorLevel = (v) => {
    color =
        if float(v: v) > 95.0 then
            "danger"
        else if float(v: v) >= 90.0 then
            "warning"
        else
            "good"

    return color
}

from(bucket: "multiapp_")
    |> range(start: -2m)
    |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
    |> filter(fn: (r) => r["_field"] == "mem_pct")
    |> group(columns: ["_time"])
    |> filter(fn: (r) => r._value > 90)
    |> toSlack(
	mapFn: (r) =>
	    ({
		channel: "roundtable-test-notifications",
		text: "${r.cluster}/${r.container_name}/${r.pod_name} at ${r._time}: ${r._value}% of memory used",
		color: colorLevel(v: r._value),
	    }),
    )()
    |> yield()
