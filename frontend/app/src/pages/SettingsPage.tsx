import { useState } from "react";
import {
  Button,
  Form,
  Input,
  Message,
  Select,
  Typography,
} from "@arco-design/web-react";
import { zh } from "../i18n/zh";
import { saveSettings, type Settings } from "../state/settings";

export function SettingsPage({
  settings,
  onSave,
}: {
  settings: Settings;
  onSave: (s: Settings) => void;
}) {
  const [form, setForm] = useState<Settings>(settings);

  return (
    <div className="page" style={{ maxWidth: 520 }}>
      <Typography.Title heading={5} style={{ marginTop: 0 }}>
        {zh.settings}
      </Typography.Title>
      <Form layout="vertical">
        <Form.Item label="API Base" required>
          <Input
            value={form.apiBase}
            onChange={(apiBase) => setForm({ ...form, apiBase })}
            placeholder="http://127.0.0.1:8088"
          />
        </Form.Item>
        <Form.Item label={zh.tokenOpt}>
          <Input.Password
            value={form.token}
            onChange={(token) => setForm({ ...form, token })}
          />
        </Form.Item>
        <Form.Item label={zh.asOf}>
          <Input
            value={form.asOf}
            onChange={(asOf) => setForm({ ...form, asOf })}
          />
        </Form.Item>
        <Form.Item label={zh.defaultAccount}>
          <Input
            value={form.accountId}
            onChange={(accountId) => setForm({ ...form, accountId })}
          />
        </Form.Item>
        <Form.Item label={zh.env}>
          <Select
            value={form.env}
            onChange={(env) => setForm({ ...form, env })}
            options={[
              { label: zh.envResearch, value: "research" },
              { label: zh.envPaper, value: "paper" },
              { label: zh.envLive, value: "live" },
            ]}
          />
        </Form.Item>
        <Button
          type="primary"
          onClick={() => {
            saveSettings(form);
            onSave(form);
            Message.success(zh.saved);
          }}
        >
          {zh.save}
        </Button>
      </Form>
    </div>
  );
}
