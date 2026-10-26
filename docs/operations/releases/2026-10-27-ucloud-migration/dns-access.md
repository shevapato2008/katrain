> 历史只读调查：下文是 UTC17:38 的递归观察。后续通过 gateway 直查两台权威 NS，已独立确认五域 AA/NOERROR、A=117.50.183.169/TTL600；见 [最终独立审核](final-independent-review.md)。权限仍为403 Forbidden.RAM，没有执行DNS写入。

# DNS 只读核查

核查时间：2026-10-26T17:38:12.223203+00:00

Provider：Alibaba Cloud DNS（阿里云云解析 DNS）。

权限结论：现有凭据对 `modelstella.com` 的只读 `DescribeDomainRecords` 调用返回 **HTTP 403 / `Forbidden.RAM`**。已停止 API 尝试；没有 DNS 写入、权限扩张、凭据变更或账户变更。控制台会话未验证，当前本机 CUA 无可操作 Chrome 窗口。

| FQDN | A 观察 | A TTL | AAAA 观察 | CNAME 观察 |
| --- | --- | --- | --- | --- |
| modelstella.com | 117.50.183.169 | 600 | 无 answer | 无 answer |
| www.modelstella.com | 117.50.183.169 | 600 | 无 answer | 无 answer |
| pitch-api-staging.modelstella.com | 117.50.183.169 | 600 | 无 answer | 无 answer |
| lobby.modelstella.com | 117.50.183.169 | 600 | 无 answer | 无 answer |
| ranked.modelstella.com | 117.50.183.169 | 600 | 无 answer | 无 answer |

观察限制：本机定向查询 `dns27.hichina.com` / `dns28.hichina.com` 的回答没有 AA，TCP 非递归查询返回递归缓存错误。因此该表是递归 DNS 观察，**不能当作控制台记录清单或直接权威回答**；“无 answer”不等于已从 zone 确认不存在。五个域名当前均观察为独立 A，`www` 未观察到 CNAME。

官方文档：[DescribeDomainRecords（域名级读取授权）](https://help.aliyun.com/en/dns/api-alidns-2015-01-09-describedomainrecords)、[AliDNS endpoint](https://www.alibabacloud.com/help/en/dns/api-alidns-2015-01-09-endpoint)、[RPC 签名机制](https://help.aliyun.com/en/sdk/product-overview/rpc-mechanism)。
