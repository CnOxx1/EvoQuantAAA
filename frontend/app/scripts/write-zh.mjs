import fs from "node:fs";
import path from "node:path";

const root = path.resolve("src");

function w(rel, content) {
  const p = path.join(root, rel);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, content, { encoding: "utf8" });
  console.log("wrote", rel);
}

// Shared Chinese via unicode escapes so the patch file itself stays ASCII-safe.
const zh = {
  notConnected: "\u672a\u8fde\u63a5\u7f51\u5173",
  notConnectedSettings:
    "\u672a\u8fde\u63a5\u7f51\u5173\uff0c\u8bf7\u5230\u300c\u8bbe\u7f6e\u300d\u914d\u7f6e API\u3002",
  todayPipe: "\u4eca\u65e5\u7ba1\u9053",
  strategy: "\u7b56\u7565",
  portfolio: "\u7ec4\u5408",
  execBatch: "\u6267\u884c\u6279\u6b21",
  kill: "\u7194\u65ad",
  openAlerts: "\u5f00\u653e\u544a\u8b66",
  level: "\u7ea7\u522b",
  source: "\u6765\u6e90",
  code: "\u4ee3\u7801",
  message: "\u6d88\u606f",
  status: "\u72b6\u6001",
  marketIntel: "\u5e02\u573a\u60c5\u62a5",
  ranks: "\u699c\u5355",
  abnormal: "\u5f02\u52a8",
  news: "\u65b0\u95fb",
  lhb: "\u9f99\u864e\u699c",
  channel: "\u9891\u9053",
  filter: "\u4ee3\u7801/\u540d\u79f0",
  all: "\u5168\u90e8",
  symbol: "\u6807\u7684",
  chg: "\u6da8\u8dcc",
  close: "\u6536\u76d8",
  amount: "\u6210\u4ea4\u989d",
  time: "\u65f6\u95f4",
  type: "\u7c7b\u578b",
  info: "\u4fe1\u606f",
  title: "\u6807\u9898",
  reason: "\u539f\u56e0",
  net: "\u51c0\u989d",
  crossSection: "\u622a\u9762\u6da8\u8dcc\u5e45",
  lhbNetYi: "\u9f99\u864e\u51c0\u989d\uff08\u4ebf\uff09",
  abnDist: "\u5f02\u52a8\u7c7b\u578b\u5206\u5e03",
  newsPlaceholder: "\u8206\u60c5\u5360\u4f4d",
  selectedKline: "\u9009\u4e2d {s} \u00b7 K\u7ebf\u5f85\u63a5\u5165",
  ctx: "\u6807\u7684\u4e0a\u4e0b\u6587",
  tradeDate: "\u4ea4\u6613\u65e5",
  hintSelected:
    "\u65e5\u7ebf / \u5206\u949f\u7ebf\u4e0e\u6280\u672f\u6307\u6807 API \u63a5\u5165\u540e\uff0c\u6b64\u7a97\u5207\u6362\u4e3a K \u7ebf\u4e3b\u56fe + \u526f\u56fe\u3002",
  hintClick:
    "\u70b9\u51fb\u5de6\u4fa7\u8868\u683c\u884c\u9009\u4e2d\u6807\u7684\u3002\u56fe\u8868\u5f53\u524d\u5c55\u793a\u622a\u9762\u5206\u5e03\uff08lightweight-charts\uff09\u3002",
  pctUp: "\u6da8\u5e45\u699c",
  pctDown: "\u8dcc\u5e45\u699c",
  volRank: "\u6210\u4ea4\u91cf\u699c",
  amtRank: "\u6210\u4ea4\u989d\u699c",
  turnRank: "\u6362\u624b\u699c",
  chOfficial: "\u5b98\u65b9\u5feb\u8baf",
  chEm: "\u4e1c\u8d22",
  chPolicy: "\u653f\u7b56",
  chForum: "\u8bba\u575b\u60c5\u7eea",
  other: "\u5176\u4ed6",
  promoteOk: "\u664b\u5347\u5df2\u63d0\u4ea4",
  promote: "\u664b\u5347",
  targetStatus: "\u76ee\u6807\u72b6\u6001",
  reasonOpt: "\u539f\u56e0\uff08\u53ef\u9009\uff09",
  version: "\u7248\u672c",
  name: "\u540d\u79f0",
  action: "\u64cd\u4f5c",
  reviewOk: "\u5df2\u63d0\u4ea4\u98ce\u63a7\u5ba1\u6838",
  holdings: "\u6301\u4ed3",
  submitReview: "\u63d0\u4ea4\u98ce\u63a7\u5ba1\u6838",
  account: "\u8d26\u6237",
  targetShares: "\u76ee\u6807\u80a1\u6570",
  priceBasis: "\u4ef7\u683c\u53e3\u5f84",
  risk: "\u98ce\u63a7",
  killUpdated: "Kill Switch \u5df2\u66f4\u65b0",
  on: "\u5f00\u542f",
  off: "\u5173\u95ed",
  opReason: "\u64cd\u4f5c\u539f\u56e0",
  confirmOff: "\u786e\u8ba4\u5173\u95ed\u7194\u65ad\uff1f",
  confirmOn: "\u786e\u8ba4\u5f00\u542f\u7194\u65ad\uff1f",
  closeKill: "\u5173\u95ed\u7194\u65ad",
  openKill: "\u5f00\u542f\u7194\u65ad",
  decisions: "\u51b3\u7b56",
  result: "\u7ed3\u679c",
  research: "\u7814\u7a76",
  factor: "\u56e0\u5b50",
  conclusion: "\u7ed3\u8bba",
  trade: "\u4ea4\u6613",
  adapter: "\u9002\u914d\u5668",
  orders: "\u59d4\u6258",
  fills: "\u6210\u4ea4",
  side: "\u4fa7",
  qty: "\u6570\u91cf",
  price: "\u4ef7\u683c",
  remaining: "\u5269\u4f59",
  pending: "Pending \u6b8b\u5dee",
  ledger: "\u8d26\u672c",
  cash: "\u73b0\u91d1",
  shares: "\u80a1\u6570",
  sellable: "\u53ef\u5356",
  opsAlerts: "\u8fd0\u7ef4\u544a\u8b66",
  settings: "\u8bbe\u7f6e",
  tokenOpt: "Bearer Token\uff08\u53ef\u9009\uff09",
  asOf: "\u4e1a\u52a1\u65e5 as_of",
  defaultAccount: "\u9ed8\u8ba4\u8d26\u6237",
  env: "\u73af\u5883",
  envResearch: "\u7814\u7a76",
  envPaper: "\u7eb8\u9762",
  envLive: "\u5b9e\u76d8",
  saved: "\u5df2\u4fdd\u5b58",
  save: "\u4fdd\u5b58",
};

w(
  "i18n/zh.ts",
  `/** Chinese copy — ASCII-safe source via unicode escapes. */\n` +
    `export const zh = ${JSON.stringify(zh, null, 2)} as const;\n` +
    `export type ZhKey = keyof typeof zh;\n`,
);

console.log("zh keys", Object.keys(zh).length);
