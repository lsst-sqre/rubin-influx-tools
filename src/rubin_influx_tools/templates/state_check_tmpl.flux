option v = {bucket: "_monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}} }

from(bucket: "{{app_bucket}}")
  |> range(start: -5m)
  |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
  |> filter(fn: (r) => (r["_field"] == "state_code"))
  |> filter(fn: (r) => (r["_value"] != 0))
  |> group(columns: ["_measurement", "_field", "container_name", "pod_name", "cluster"])
  |> aggregateWindow(every: 30s, fn: max, createEmpty: false)
  |> map(fn: (r) => ({
             _time: r._time,
             _measurement: r._measurement,
             _field: "pod_state",
             cluster: r.cluster,
             container_name: r.container_name,
             application: "{{app_bucket}}",
             pod_name: r.pod_name,
             phase: r.phase,
	     phase_reason: "",
             state: r.state,
	     state_code: r._value,
	     state_reason: "",
             readiness: r.readiness,
	     alerted: false
             })
             )
  |> to(bucket: "multiapp_", org: "square")
