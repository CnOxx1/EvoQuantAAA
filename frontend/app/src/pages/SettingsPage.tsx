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

  function submit(e: FormEvent) {
    e.preventDefault();
    saveSettings(draft);
    onChange(draft);
  }

  return (
    <div>
      <h1>Settings</h1>
      <p className="lede">
        API Base / Token / 默认账户 / 环境徽章。设置仅存本机
        localStorage，不进库。
      </p>
      <form className={`${styles.form} ${styles.panel}`} onSubmit={submit}>
        <label>
          API Base
          <input
            value={draft.apiBase}
            onChange={(e) => setDraft({ ...draft, apiBase: e.target.value })}
            required
          />
        </label>
        <label>
          Bearer Token
          <input
            type="password"
            value={draft.apiToken}
            onChange={(e) => setDraft({ ...draft, apiToken: e.target.value })}
            placeholder="ASHARE_API_TOKEN"
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
          as-of
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
            <option value="research">research</option>
            <option value="paper">paper</option>
            <option value="live">live（UI 锁死提示）</option>
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
        </div>
      </form>
    </div>
  );
}
