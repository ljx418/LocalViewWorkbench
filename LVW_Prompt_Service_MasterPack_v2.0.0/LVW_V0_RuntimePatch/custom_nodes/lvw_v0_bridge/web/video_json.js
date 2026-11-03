// Keep the server's canonical source JSON, including integer PTS beyond 2^53.
// Editors operate on draft strings; source provenance is never edited here.
function stringEnd(text, start) {
  for (let i = start + 1; i < text.length; i++) {
    if (text[i] === "\\") i++;
    else if (text[i] === '"') return i + 1;
  }
  throw new Error("来源 JSON 字符串不完整，未导出。");
}

const space = (text, start) => {
  while (/\s/.test(text[start] || "") && start < text.length) start++;
  return start;
};

function valueEnd(text, start) {
  if (text[start] === '"') return stringEnd(text, start);
  if (text[start] === "{" || text[start] === "[") {
    let depth = 0;
    for (let i = start; i < text.length; i++) {
      if (text[i] === '"') i = stringEnd(text, i) - 1;
      else if (text[i] === "{" || text[i] === "[") depth++;
      else if ((text[i] === "}" || text[i] === "]") && --depth === 0) return i + 1;
    }
    throw new Error("来源 JSON 容器不完整，未导出。");
  }
  let end = start;
  while (end < text.length && !/[\s,}\]]/.test(text[end])) end++;
  return end;
}

export function rawMember(text, path) {
  JSON.parse(text); // Validate the whole response; no eval or permissive parser.
  if (!Array.isArray(path) || path.length === 0) throw new Error("缺少来源字段路径。");
  let raw = text;
  for (const key of path) {
    let i = space(raw, 0), found = null;
    if (raw[i++] !== "{") throw new Error("来源字段不是 JSON 对象。");
    while ((i = space(raw, i)) < raw.length && raw[i] !== "}") {
      const keyEnd = stringEnd(raw, i), name = JSON.parse(raw.slice(i, keyEnd));
      i = space(raw, keyEnd);
      if (raw[i++] !== ":") throw new Error("来源字段格式无效。");
      const start = space(raw, i), end = valueEnd(raw, start);
      if (name === key) {
        if (found !== null) throw new Error("来源字段重复，未导出。");
        found = raw.slice(start, end);
      }
      i = space(raw, end);
      if (raw[i] === ",") i++;
      else break;
    }
    if (found === null) throw new Error("缺少采纳来源，未导出。");
    raw = found;
  }
  return raw;
}

export function resultJson(result, sourceJson = null) {
  if (sourceJson === null) return JSON.stringify(result, null, 2) + "\n";
  if (typeof sourceJson !== "string" || !Object.prototype.hasOwnProperty.call(result, "source")
      || JSON.stringify(JSON.parse(sourceJson)) !== JSON.stringify(result.source)) {
    throw new Error("来源与采纳快照不一致，未导出。");
  }
  const entries = [];
  for (const [key, value] of Object.entries(result)) {
    const raw = key === "source" ? sourceJson : JSON.stringify(value, null, 2);
    if (raw !== undefined) entries.push(`  ${JSON.stringify(key)}: ${raw.replace(/\n/g, "\n  ")}`);
  }
  return "{\n" + entries.join(",\n") + "\n}\n";
}
