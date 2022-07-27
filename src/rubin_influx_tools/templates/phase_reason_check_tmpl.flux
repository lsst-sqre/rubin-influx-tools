option v = {bucket: "_monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}} }

stateCode = (v) => {
    code =
        if v == "running" then
             0
        else if v == "terminated" then
            1
        else if v == "waiting" then
            2
        else
            3

    return code
}

from(bucket: "{{app_bucket}}")
  |> range(start: -5m)
  |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
  |> filter(fn: (r) => (r["_field"] == "phase_reason"))
  |> group(columns: ["_measurement", "_field", "container_name", "pod_name", "cluster"])
  |> aggregateWindow(every: 30s, fn: last, createEmpty: false)
  |> map(fn: (r) => ({
             _time: r._time,
             _measurement: r._measurement,
             _field: "pod_state",
             _value: stateCode(v: r.state),
             cluster: r.cluster,
             container_name: r.container_name,
             application: "{{app_bucket}}",
             pod_name: r.pod_name,
             phase: r.phase,
             phase_reason: r._value,
             state: r.state,
             state_code: stateCode(v: r.state),
             state_reason: "",
             readiness: r.readiness,
             alerted: false
             })
             )
  |> to(bucket: "multiapp_", org: "square")
