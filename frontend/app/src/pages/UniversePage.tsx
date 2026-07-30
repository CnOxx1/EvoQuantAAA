import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Drawer,
  Grid,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  getUniverseSnapshot,
  listUniverseSnapshots,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { HorizontalBars } from "../components/HorizontalBars";
import { PieChart } from "../components/PieChart";
import { TimeSeriesChart } from "../components/TimeSeriesChart";
import { STATUS_COLORS, countBy } from "../lib/chartAgg";
import { toChartTime } from "../lib/chartTime";
import { n, s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

export function UniversePage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [code, setCode] = useState<string | undefined>();
  const [id, setId] = useState("");

  const q = useQuery({
    queryKey: ["universe", cfg.apiBase, code],
    queryFn: () => listUniverseSnapshots(cfg, { universeCode: code, limit: 80 }),
    enabled: connected,
  });
  const detailQ = useQuery({
    queryKey: ["universe-detail", cfg.apiBase, id],
    queryFn: () => getUniverseSnapshot(cfg, id),
    enabled: connected && Boolean(id),
  });

  const members = (detailQ.data?.members as JsonMap[] | undefined) ?? [];

  const statusSlices = useMemo(
    () =>
      countBy(q.data ?? [], (r) => s(r.status, "unknown"), {
        colors: STATUS_COLORS,
      }),
    [q.data],
  );

  const memberTrend = useMemo(() => {
    const rows = [...(q.data ?? [])]
      .filter((r) => !code || s(r.universe_code) === code)
      .sort((a, b) => s(a.as_of_date).localeCompare(s(b.as_of_date)));
    const byCode = new Map<string, { time: string | number; value: number }[]>();
    for (const r of rows) {
      const uc = s(r.universe_code, "?");
      const t = toChartTime(s(r.as_of_date));
      const v = Number(r.member_count);
      if (t == null || !Number.isFinite(v)) continue;
      if (!byCode.has(uc)) byCode.set(uc, []);
      byCode.get(uc)!.push({ time: t, value: v });
    }
    const palette = ["#165dff", "#0fc6c2", "#722ed1", "#ff7d00"];
    return Array.from(byCode.entries()).map(([k, data], i) => ({
      id: k,
      color: palette[i % palette.length],
      data,
      lineWidth: 2 as const,
    }));
  }, [q.data, code]);

  const industrySlices = useMemo(
    () => countBy(members, (m) => s(m.industry_name, "未分类")).slice(0, 12),
    [members],
  );

  const stSlices = useMemo(() => {
    let st = 0;
    let normal = 0;
    for (const m of members) {
      if (Number(m.is_st) === 1) st += 1;
      else normal += 1;
    }
    return [
      { id: "normal", label: "正常", value: normal, color: "#165dff" },
      { id: "st", label: "ST", value: st, color: "#f53f3f" },
    ].filter((x) => x.value > 0);
  }, [members]);

  const weightBars = useMemo(
    () =>
      members
        .map((m) => ({
          id: s(m.symbol, ""),
          label: s(m.symbol),
          value: Number(m.index_weight) || 0,
        }))
        .filter((x) => x.value > 0)
        .sort((a, b) => b.value - a.value)
        .slice(0, 15),
    [members],
  );

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">未连接网关</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Space style={{ marginBottom: 12 }}>
        <Typography.Title heading={5} style={{ margin: 0 }}>
          Universe 快照
        </Typography.Title>
        <Select
          size="small"
          allowClear
          placeholder="universe_code"
          style={{ width: 180 }}
          value={code}
          onChange={setCode}
          options={[
            { label: "TOP100", value: "TOP100" },
            { label: "SECTOR_LEADERS", value: "SECTOR_LEADERS" },
            { label: "HS300", value: "HS300" },
            { label: "ZZ500", value: "ZZ500" },
          ]}
        />
      </Space>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        security_master · 日快照头与成员
      </Typography.Paragraph>

      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col xs={24} md={16}>
          <TimeSeriesChart
            title="成员数趋势"
            subtitle={code || "全部 universe_code"}
            lines={memberTrend}
            height={200}
            emptyHint="无快照序列"
            loading={q.isLoading}
          />
        </Col>
        <Col xs={24} md={8}>
          <PieChart
            title="快照状态"
            slices={statusSlices}
            height={200}
            emptyHint="暂无快照"
            loading={q.isLoading}
          />
        </Col>
      </Row>

      <Table
        rowKey={(r) => s(r.universe_snapshot_id)}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        pagination={{ pageSize: 20, size: "mini", showTotal: true }}
        onRow={(r) => ({
          onClick: () => setId(s(r.universe_snapshot_id, "")),
        })}
        columns={[
          {
            title: "snapshot",
            dataIndex: "universe_snapshot_id",
            width: 180,
            render: (v) => <code>{s(v)}</code>,
          },
          { title: "代码", dataIndex: "universe_code", render: (v) => s(v) },
          {
            title: "as_of",
            dataIndex: "as_of_date",
            width: 110,
            render: (v) => s(v),
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 100,
            render: (v) => <Tag size="small">{s(v)}</Tag>,
          },
          {
            title: "成员数",
            dataIndex: "member_count",
            width: 90,
            render: (v) => n(v, 0),
          },
          { title: "创建", dataIndex: "created_at", render: (v) => s(v) },
        ]}
      />

      <Drawer
        width={820}
        title={`Universe ${id}`}
        visible={Boolean(id)}
        onCancel={() => setId("")}
        footer={null}
      >
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Typography.Text>
            {s(detailQ.data?.universe_code)} @ {s(detailQ.data?.as_of_date)} ·{" "}
            <Tag size="small">{s(detailQ.data?.status)}</Tag>
          </Typography.Text>
          <Row gutter={12}>
            <Col xs={24} md={12}>
              <PieChart
                title="行业构成"
                slices={industrySlices}
                height={240}
                emptyHint={detailQ.isLoading ? "加载中…" : "无行业字段"}
                loading={detailQ.isLoading}
              />
            </Col>
            <Col xs={24} md={12}>
              <PieChart
                title="ST 占比"
                slices={stSlices}
                height={120}
                emptyHint="无成员"
                loading={detailQ.isLoading}
              />
              <div style={{ marginTop: 8 }}>
                <HorizontalBars
                  title="指数权重 Top"
                  items={weightBars}
                  height={160}
                  formatValue={(v) => n(v, 4)}
                  emptyHint="无权重（等权 Universe 常见）"
                  loading={detailQ.isLoading}
                />
              </div>
            </Col>
          </Row>
          <Table
            rowKey={(r) => s(r.symbol)}
            size="mini"
            loading={detailQ.isLoading}
            data={members}
            pagination={{ pageSize: 15, size: "mini" }}
            columns={[
              { title: "代码", dataIndex: "symbol", render: (v) => s(v) },
              { title: "名称", dataIndex: "name", render: (v) => s(v) },
              { title: "行业", dataIndex: "industry_name", render: (v) => s(v) },
              {
                title: "ST",
                dataIndex: "is_st",
                width: 50,
                render: (v) => (Number(v) === 1 ? "Y" : ""),
              },
              {
                title: "权重",
                dataIndex: "index_weight",
                render: (v) => (v == null ? "—" : n(v, 4)),
              },
            ]}
          />
        </Space>
      </Drawer>
    </div>
  );
}
