option v = {bucket: "_monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

option task = {name: "{{taskname}}", every: {{every}}, offset: {{offset}} }

extractStateCode = (v) => {
  code =
    if v == "running" then
        0
    else if v == "terminated" then
        1
    else if v == "waiting" then
        2
    else 3
  return code
}

from(bucket: "{{app_bucket}}")
  |> range(start: -5m)
  |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
  |> filter(fn: (r) => (r._field == "state_code" or r._field == "phase_reason" or r._field == "state_reason"))
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  // Ensure state code
  |> map(
    fn: (r) => ({ r with
        state_code: if exists r.state_code then
            r.state_code
        else
            extractStateCode(v: r.state)
      })
    )
  // Filter on nonn-running state
  |> filter(fn: (r) => r.state_code != 0)
  // Drop unused columns
  |> drop(columns: ["host", "namespace", "node_name"])
  // canonicalize shape with state/phase reason
  |> map(
    fn: (r) => ({ r with 
        phase_reason: if exists r.phase_reason then 
            r.phase_reason
        else
            ""
      })
    )
  |> map(
    fn: (r) => ({ r with 
        state_reason: if exists r.state_reason then 
            r.state_reason
        else
            ""
    })
  )
  // Pretend it was a pod_state metric all along
  |> map(fn: (r) => ({ r with _field: "pod_state"}))
  // Why doesn't the _value map work?
  |> map(fn: (r) => ({ r with _value: r.pod_state}))
  |> map(fn: (r) => ({ r with application: "{{app_bucket}}" }))
  |> map(fn: (r) => ({ r with alerted: false }))
  |> group(columns: ["_measurement", "_field", "_value", "_time", "application", "alerted", "cluster", "container_name", "phase", "phase_reason", "pod_name", "readiness", "state", "state_code", "state_reason"])
  // Remove duplicate timestamps
  |> distinct(column: "_time")
  |> to(bucket: "multiapp_", org: "square")

