import type { ReactNode } from "react";
import styles from "./DataTable.module.css";

export function DataTable({
  headers,
  children,
  empty,
  isEmpty,
}: {
  headers: string[];
  children: ReactNode;
  empty?: string;
  isEmpty?: boolean;
}) {
  return (
    <div className={styles.wrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
      {isEmpty ? <p className={styles.empty}>{empty || "暂无数据"}</p> : null}
    </div>
  );
}
