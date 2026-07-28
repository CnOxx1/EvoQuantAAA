import fs from "node:fs";

const p = "src/i18n/zh.ts";
let s = fs.readFileSync(p, "utf8");
const extras = {
  comingSoon: "\u5373\u5c06\u63a5\u5165",
  kline: "\u65e5\u7ebf K",
  klineQfq: "\u524d\u590d\u6743\u65e5\u7ebf",
  noBars:
    "\u8be5\u6807\u7684\u6682\u65e0 processed \u65e5\u7ebf\uff0c\u8bf7\u5148 data_process equity_1d",
  barsLoading: "\u6b63\u5728\u52a0\u8f7d K \u7ebf\u2026",
};
for (const [k, v] of Object.entries(extras)) {
  if (s.includes(`"${k}"`)) continue;
  s = s.replace(/\n\} as const/, `,\n  "${k}": "${v}"\n} as const`);
}
fs.writeFileSync(p, s, "utf8");
console.log("updated zh");
