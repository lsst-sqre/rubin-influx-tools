import "strings"

buckets()
 |> rename(columns: {"name": "_value"})
 |> keep(columns: ["_value"])
 |> filter(fn: (r) => (not strings.hasPrefix(prefix:"_", v: r._value)
                        and not strings.hasSuffix(suffix:"_", v: r._value)))
