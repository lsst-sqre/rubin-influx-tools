import "slack"
import "influxdata/influxdb/secrets"

option v = {bucket: "_monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}}}

slackurl = secrets.get(key: "slack_notify_url")
toSlack = slack.endpoint(url: slackurl)

from(bucket: "multiapp_")
    |> range(start: -5m)
    |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
    |> filter(fn: (r) => r["_field"] == "differential_restarts")
    |> group(columns: ["_time"])
    |> filter(fn: (r) => r._value != 0)
    |> toSlack(
	mapFn: (r) =>
	    ({
		channel: "roundtable-test-notifications",
		text: "Restart(s) for ${r.cluster}/${r.application}/${r.pod_name} (${r.container_name}) at ${r._time}: ${r._value}",
		color: "danger",
	    }),
    )()
    |> yield()
