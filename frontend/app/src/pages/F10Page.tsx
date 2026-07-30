import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AutoComplete,
  Card,
  Descriptions,
  Grid,
  Input,
  Space,
  Typography,
} from "@arco-design/web-react";
import {
  getF10,
  searchSecurities,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { fmtAmt, n, s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

function kv(obj: JsonMap | null | undefined) {
  if (!obj) return [];
  return Object.entries(obj).map(([label, value]) => ({
    label,
    value: s(value),
  }));
}

export function F10Page({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [symbol, setSymbol] = useState("");
  const [q, setQ] = useState("");

  const searchQ = useQuery({
    queryKey: ["f10-search", cfg.apiBase, q, settings.asOf],
    queryFn: () =>
      searchSecurities(cfg, { q, asOf: settings.asOf, limit: 10 }),
    enabled: connected && q.trim().length >= 1,
  });

  const f10Q = useQuery({
    queryKey: ["f10", cfg.apiBase, symbol, settings.asOf],
    queryFn: () => getF10(cfg, symbol, settings.asOf),
    enabled: connected && Boolean(symbol),
  });

  const options = useMemo(
    () =>
      (searchQ.data?.items ?? []).map((it) => ({
        value: String(it.symbol ?? ""),
        name: `${it.symbol} ${it.name ?? ""}`.trim(),
      })),
    [searchQ.data],
  );

  const d = f10Q.data;
  const val = (d?.valuation as JsonMap | undefined) ?? undefined;
  const fund = (d?.fundamentals as JsonMap | undefined) ?? undefined;

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">未连接网关</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Typography.Title heading={5} style={{ marginTop: 0 }}>
        F10 资料
      </Typography.Title>
      <Space style={{ marginBottom: 16 }}>
        <AutoComplete
          allowClear
          placeholder="代码/名称"
          style={{ width: 260 }}
          data={options}
          value={q}
          onSearch={setQ}
          onChange={setQ}
          onSelect={(v) => {
            setSymbol(String(v));
            setQ(String(v));
          }}
        />
        <Input
          size="small"
          style={{ width: 120 }}
          value={symbol}
          onChange={setSymbol}
          placeholder="symbol"
          onPressEnter={() => setSymbol(symbol.trim())}
        />
        <Typography.Text type="secondary">as_of {settings.asOf}</Typography.Text>
      </Space>

      {!symbol ? (
        <Typography.Text type="secondary">搜索并选择标的</Typography.Text>
      ) : f10Q.isLoading ? (
        <Typography.Text type="secondary">加载中…</Typography.Text>
      ) : !d ? (
        <Typography.Text type="secondary">无 F10 数据</Typography.Text>
      ) : (
        <Row gutter={[12, 12]}>
          <Col span={12}>
            <Card size="small" title="上市资料">
              <Descriptions
                column={1}
                size="mini"
                data={kv(d.listing as JsonMap | undefined)}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title="行业">
              <Descriptions
                column={1}
                size="mini"
                data={kv(d.industry as JsonMap | undefined)}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title="估值">
              <Descriptions
                column={2}
                size="mini"
                data={[
                  { label: "日期", value: s(val?.trade_date) },
                  { label: "PE-TTM", value: n(val?.pe_ttm, 2) },
                  { label: "PB", value: n(val?.pb, 2) },
                  { label: "PS-TTM", value: n(val?.ps_ttm, 2) },
                  { label: "总市值", value: fmtAmt(val?.total_mv) },
                  { label: "流通市值", value: fmtAmt(val?.float_mv) },
                ]}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title="基本面 PIT">
              <Descriptions
                column={2}
                size="mini"
                data={[
                  { label: "报告期", value: s(fund?.report_period) },
                  { label: "公告日", value: s(fund?.publish_date) },
                  { label: "营收", value: fmtAmt(fund?.revenue) },
                  { label: "净利", value: fmtAmt(fund?.net_profit) },
                  { label: "ROE", value: n(fund?.roe, 2) },
                  { label: "EPS", value: n(fund?.eps, 3) },
                ]}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title="股东户数">
              <Descriptions
                column={1}
                size="mini"
                data={kv(d.holders as JsonMap | undefined)}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title="股本">
              <Descriptions
                column={1}
                size="mini"
                data={kv(d.share_capital as JsonMap | undefined)}
              />
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
}
