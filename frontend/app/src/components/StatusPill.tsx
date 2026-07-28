import type { ReactNode } from "react";
import styles from "./StatusPill.module.css";

export type PillTone = "ok" | "degraded" | "failed" | "skipped" | "neutral" | "info";

const TONE_CLASS: Record<PillTone, string> = {
  ok: styles.ok,
  degraded: styles.degraded,
  failed: styles.failed,
  skipped: styles.skipped,
  neutral: styles.neutral,
  info: styles.info,
};

export function StatusPill({
  tone = "neutral",
  children,
}: {
  tone?: PillTone;
  children: ReactNode;
}) {
  return <span className={`${styles.pill} ${TONE_CLASS[tone]}`}>{children}</span>;
}

export function toneFromStatus(status?: string): PillTone {
  const s = (status || "").toLowerCase();
  if (["ok", "approved", "committed", "live", "filled", "success"].includes(s)) {
    return "ok";
  }
  if (["degraded", "warning", "paper", "running", "draft"].includes(s)) {
    return "degraded";
  }
  if (["failed", "rejected", "error", "blocked", "retired"].includes(s)) {
    return "failed";
  }
  if (["skipped", "superseded"].includes(s)) return "skipped";
  if (["backtested"].includes(s)) return "info";
  return "neutral";
}
