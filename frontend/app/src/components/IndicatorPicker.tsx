import { useMemo, useState } from "react";
import { Drawer, Input, Message, Tag, Typography } from "@arco-design/web-react";
import {
  MAX_OVERLAY,
  MAX_SUB,
  placementOf,
  toggleCode,
  type IndicatorMetaItem,
} from "../lib/indicatorCatalog";
import { zh } from "../i18n/zh";
import styles from "./IndicatorPicker.module.css";

export function IndicatorPicker({
  visible,
  onClose,
  catalog,
  available,
  active,
  onChange,
}: {
  visible: boolean;
  onClose: () => void;
  catalog: IndicatorMetaItem[];
  /** 当前标的有数据的 code 集合；空则不灰显 */
  available: Set<string>;
  active: string[];
  onChange: (next: string[]) => void;
}) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");

  const categories = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of catalog) m.set(c.category, c.category_zh || c.category);
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1], "zh"));
  }, [catalog]);

  const metaByCode = useMemo(() => {
    const m = new Map<string, IndicatorMetaItem>();
    for (const c of catalog) m.set(c.code, c);
    return m;
  }, [catalog]);

  const filtered = useMemo(() => {
    const needle = q.trim().toUpperCase();
    return catalog.filter((c) => {
      if (cat !== "all" && c.category !== cat) return false;
      if (needle && !c.code.toUpperCase().includes(needle)) return false;
      return true;
    });
  }, [catalog, q, cat]);

  const overlayN = active.filter(
    (c) => placementOf(c, metaByCode) === "overlay",
  ).length;
  const subN = active.filter((c) => placementOf(c, metaByCode) === "sub").length;

  const flip = (code: string) => {
    const { next, msg } = toggleCode(active, code, metaByCode);
    if (msg) Message.warning(msg);
    onChange(next);
  };

  return (
    <Drawer
      width={420}
      title={zh.indPickerTitle}
      visible={visible}
      onCancel={onClose}
      footer={null}
      unmountOnExit
    >
      <div className={styles.toolbar}>
        <Input.Search
          allowClear
          placeholder={zh.indSearch}
          value={q}
          onChange={setQ}
        />
        <div className={styles.meta}>
          <span>
            {zh.indSelected} {active.length} · {zh.indOverlay} {overlayN}/
            {MAX_OVERLAY} · {zh.indSub} {subN}/{MAX_SUB}
          </span>
          <span>
            {zh.indCatalog} {catalog.length}
          </span>
        </div>
        {active.length > 0 ? (
          <div className={styles.tags}>
            {active.map((code) => (
              <Tag
                key={code}
                closable
                size="small"
                color={
                  placementOf(code, metaByCode) === "overlay" ? "orangered" : "arcoblue"
                }
                onClose={() => onChange(active.filter((c) => c !== code))}
              >
                {code}
              </Tag>
            ))}
          </div>
        ) : null}
        <div className={styles.cats}>
          <button
            type="button"
            className={`${styles.cat} ${cat === "all" ? styles.catOn : ""}`}
            onClick={() => setCat("all")}
          >
            {zh.all}
          </button>
          {categories.map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`${styles.cat} ${cat === id ? styles.catOn : ""}`}
              onClick={() => setCat(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.list}>
        {filtered.length === 0 ? (
          <Typography.Text type="secondary">{zh.indEmpty}</Typography.Text>
        ) : (
          filtered.map((item) => {
            const on = active.includes(item.code);
            const has =
              available.size === 0 || available.has(item.code);
            return (
              <button
                key={item.code}
                type="button"
                className={`${styles.row} ${on ? styles.rowOn : ""} ${
                  has ? "" : styles.rowDim
                }`}
                onClick={() => flip(item.code)}
                title={
                  has
                    ? `${item.category_zh} · ${item.placement}`
                    : zh.indNoData
                }
              >
                <span className={styles.code}>{item.code}</span>
                <span className={styles.side}>
                  <span className={styles.badge}>
                    {item.placement === "overlay" ? zh.indOverlay : zh.indSub}
                  </span>
                  {!has ? (
                    <span className={styles.miss}>{zh.indNoDataShort}</span>
                  ) : (
                    <span className={styles.cnt}>{item.count}</span>
                  )}
                </span>
              </button>
            );
          })
        )}
      </div>
    </Drawer>
  );
}
