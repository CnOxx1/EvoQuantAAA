import { Link } from "react-router-dom";
import styles from "./pages.module.css";

export function PlaceholderPage({
  title,
  phase,
  blurb,
}: {
  title: string;
  phase: string;
  blurb: string;
}) {
  return (
    <div>
      <h1>{title}</h1>
      <p className="lede">{blurb}</p>
      <section className={styles.panel}>
        <p>
          本页为 <strong>{phase}</strong> 占位。F1
          已落地 Overview / Strategies / Portfolio / Risk / Settings。
        </p>
        <p className={styles.muted} style={{ marginTop: "0.75rem" }}>
          需要对应 gateway 列表 API 后再深化。可先用{" "}
          <Link to="/">Overview</Link> 与静态{" "}
          <code className="mono">frontend/console</code>。
        </p>
      </section>
    </div>
  );
}
