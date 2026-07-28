import fs from "node:fs";
import path from "node:path";

const root = path.resolve("src");

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (/\.(tsx|ts|css|html)$/.test(name)) out.push(p);
  }
  return out;
}

for (const p of walk(root)) {
  const s = fs.readFileSync(p, "utf8");
  const hits = s.split(/\n/).filter((l) => /\?\?\?/.test(l) || /"\?\?"/.test(l));
  if (hits.length) {
    console.log(p);
    for (const h of hits.slice(0, 8)) console.log(" ", h.trim());
  }
}
