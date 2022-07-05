from(bucket: "ingress_nginx")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["cluster"] == v.cluster)
  |> filter(fn: (r) => r["namespace"] == v.K8s_application)
  |> filter(fn: (r) => r["_measurement"] == "prometheus_controller")
  |> filter(fn: (r) => r["_field"] == "nginx_ingress_controller_requests")
  |> drop(columns: ["_measurement", "_field", "cluster", "namespace", "_start", "_stop", "controller_class", "controller_namespace", "controller_pod", "host", "ingress", "namespace", "prometheus_app", "url"])
  |> map(fn: (r) => ({r with status: int(v: r.status)}))
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
  |> yield(name: "max")