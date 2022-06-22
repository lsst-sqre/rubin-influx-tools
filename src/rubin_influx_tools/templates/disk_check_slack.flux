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
        else if float(v: v) >= 85.0 then
            "warning"
        else
            "good"

    return color
}

from(bucket: "roundtable_internal_")
    |> range(start: -2m)
    |> filter(fn: (r) => r["_measurement"] == "disk")
    |> filter(fn: (r) => r["_field"] == "used_percent")
    |> group(columns: ["_time"])
    |> filter(fn: (r) => r._value > 85.0)
    |> toSlack(
	mapFn: (r) =>
	    ({
		channel: "roundtable-test-notifications",
		text: "${r.host}: ${r.path} at ${r._value}% used",
		color: colorLevel(v: r._value),
	    }),
    )()
    |> yield()
