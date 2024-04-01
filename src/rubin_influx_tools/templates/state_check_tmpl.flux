option v = {bucket: "monitoring", timeRangeStart: -1h, timeRangeStop: now(), windowPeriod: 10000ms}

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
  // Filter on non-running state
  |> filter(fn: (r) => r.state_code != 0)
  // Drop unused columns
  |> drop(columns: ["host", "namespace", "node_name"])
  // canonicalize shape with state/phase reason
  |> map(
    fn: (r) => ({ r with
        state_reason: if exists r.state_reason then
            r.state_reason
        else
            "n/a"
      })
    )
  |> map(
    fn: (r) => ({ r with
        phase_reason: if exists r.phase_reason then
            r.phase_reason
        else
            "n/a"
      })
    )
  |> map(
    fn: (r) => ({ r with
        alerted: if exists r.alerted then
            r.alerted
        else
            false
    })
  )
  // Filter on not-successfully-completed
  // Sometimes K8s can take a little while to update "Running", but it's
  // still a successful completion.
  // We also sometimes get Pending and Completed--maybe it exits so fast
  // that it never goes to Running and thence to Succeeded?
  |> filter(fn: (r) => not (r.state_code == 1 and r.state_reason == "Completed" and (r.phase == "Succeeded" or r.phase == "Running" or r.phase == "Pending")))
  // For now, filter out waiting/Pending/ContainerCreating.  We eventually
  // need some way of deciding it's taking too long and alerting on that.
  |> filter(fn: (r) => not (r.state_code == 2 and r.state_reason == "ContainerCreating" and r.phase == "Pending"))
  // Pretend it was a pod_state metric all along
  |> map(fn: (r) => ({ r with _field: "pod_state"}))
  |> map(fn: (r) => ({ r with application: "{{app_bucket}}" }))
  |> map(fn: (r) => ({ r with strtime: string(v: r._time) }))
  |> map(fn: (r) => ({ r with message: "${r.cluster}/${r.application}/${r.pod_name} (${r.container_name}) at ${r.strtime}: state ${r.state}, phase ${r.phase}, readiness ${r.readiness}. State reason: ${r.state_reason}, phase reason: ${r.phase_reason}" }))
  |> map(fn: (r) => ({ r with alerted: false }))
  |> group(columns: ["_measurement", "_field", "_value", "_time", "alerted", "application", "cluster", "container_name", "message", "phase", "phase_reason", "pod_name", "readiness", "state", "state_code", "state_reason"])
  // Remove duplicate messages
  |> drop(columns: ["_value"])
  |> distinct(column: "message")
  // Replace _value with correct one
  |> map(fn: (r) => ({ r with _value: r.state_code}))
  |> to(bucket: "multiapp_", org: "square")
