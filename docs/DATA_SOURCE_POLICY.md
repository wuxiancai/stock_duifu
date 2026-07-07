# 数据源策略

统一多源切换系统覆盖的主流源：TuShare、AkShare、东方财富、腾讯行情、新浪行情、网易财经、同花顺、Baostock、巨潮资讯、交易所/指数官方源。

## 默认数据域策略

- `market_snapshot`：TuShare -> AkShare。
- `stock_daily`：TuShare -> Baostock -> 东方财富 -> 网易 -> 新浪 -> 腾讯。
- `index_daily`：TuShare -> 东方财富 -> 新浪 -> 腾讯 -> 官方源。
- `limit_snapshot`：东方财富 -> 同花顺 -> AkShare -> `stock_daily.pct_chg` 推导兜底。
- `sector_daily`：东方财富 -> 同花顺 -> 巨潮/申万行业分类聚合 -> 同日缓存。
- `sector_membership`：东方财富 -> 同花顺 -> 巨潮/申万行业分类 -> 历史缓存。
- `realtime_quote`：新浪直连 -> 东方财富直连 -> 腾讯直连 -> AkShare Eastmoney -> AkShare Sina。
- `announcement`：巨潮资讯 -> 交易所公告 -> 东方财富 -> 新浪/同花顺补充。

## 硬规则

- 业务代码不直接绑定单一源，统一通过 `backend/app/data_source_router.py`。
- 首选源失败、超时、空数据、脏数据时切备用源。
- 所有源失败且无安全缓存/推导时，不生成交易计划。
- 推导数据必须保留 `inferred` 语义，不允许伪装成真实源。
