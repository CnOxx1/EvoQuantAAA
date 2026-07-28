import { useState, type FormEvent } from "react";
import {
  DEFAULT_SETTINGS,
  type Settings,
  saveSettings,
} from "../state/settings";
import styles from "./pages.module.css";

export function SettingsPage({
  settings,
  onChange,
}: {
  settings: Settings;
  onChange: (next: Settings) => void;
}) {
  const [draft, setDraft] = useState(settings);
  const [saved, setSaved] = useState(false);

  function submit(e: FormEvent) {
    e.preventDefault();
    saveSettings(draft);
    onChange(draft);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1500);
  }

  return (
    <div>
      <h1>设置</h1>
      <p className="lede">
        连接参数仅保存在本机浏览器，不会写入业务库。若本机 8080
        被代理占用，请改为网关实际端口（例如 8088）。
      </p>
      <form className={`${styles.form} ${styles.panel}`} onSubmit={submit}>
        <label>
          网关地址（API Base）
          <input
            value={draft.apiBase}
            onChange={(e) => setDraft({ ...draft, apiBase: e.target.value })}
            required
            placeholder="http://127.0.0.1:8088"
          />
        </label>
        <label>
          访问令牌（Bearer Token）
          <input
            type="password"
            value={draft.apiToken}
            onChange={(e) => setDraft({ ...draft, apiToken: e.target.value })}
            placeholder="未设置 ASHARE_API_TOKEN 时可留空"
            autoComplete="off"
          />
        </label>
        <label>
          默认账户
          <input
            className="mono"
            value={draft.accountId}
            onChange={(e) => setDraft({ ...draft, accountId: e.target.value })}
          />
        </label>
        <label>
          业务日（as-of）
          <input
            type="date"
            value={draft.asOf}
            onChange={(e) => setDraft({ ...draft, asOf: e.target.value })}
          />
        </label>
        <label>
          环境徽章
          <select
            value={draft.env}
            onChange={(e) =>
              setDraft({
                ...draft,
                env: e.target.value as Settings["env"],
              })
            }
          >
            <option value="research">研究</option>
            <option value="paper">纸面</option>
            <option value="live">实盘（界面锁定提示）</option>
          </select>
        </label>
        <div className={styles.btnRow}>
          <button type="submit" className={styles.primary}>
            保存
          </button>
          <button
            type="button"
            className={styles.secondary}
            onClick={() => {
              setDraft({ ...DEFAULT_SETTINGS });
              saveSettings(DEFAULT_SETTINGS);
              onChange(DEFAULT_SETTINGS);
            }}
          >
            恢复默认
          </button>
          {saved ? <span className={styles.muted}>已保存</span> : null}
        </div>
      </form>
    </div>
  );
}
