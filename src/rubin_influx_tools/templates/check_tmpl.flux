import "influxdata/influxdb/monitor"
import "influxdata/influxdb/v1"

data =
    from(bucket: "multiapp_")
        |> range(start: -1m)
        |> filter(fn: (r) => r["_measurement"] == "kubernetes_pod_container")
        |> filter(fn: (r) => r["_field"] == "differential_restarts")
        |> aggregateWindow(every: 1m, fn: last, createEmpty: false)

crit = (r) => r["restarts_total"] != 0.0
messageFn = (r) => "Check: ${r._check_name}: ${r._value} restarts for ${r.cluster}/${r.container_name}/${r.pod_name}"

data |> v1["fieldsAsCols"]() |> monitor["check"](data: check, messageFn: messageFn, crit: crit)
