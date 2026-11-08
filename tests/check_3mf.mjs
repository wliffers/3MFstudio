// Prueft 3MF-Dateien mit dem MCP-Server des 3MF-Konsortiums (lib3mf, strenger Leser + Vorpruefung).
// Aufruf: node check_3mf.mjs <datei.3mf> [...]   Ausgabe: eine JSON-Zeile je Datei.
import { Client } from "../conformance/3mf-mcp/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js";
import { StdioClientTransport } from "../conformance/3mf-mcp/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const transport = new StdioClientTransport({ command: process.execPath, args: [join(here, "..", "conformance", "3mf-mcp", "dist", "cli.js")] });
const client = new Client({ name: "3mfstudio-check", version: "1.0.0" });
await client.connect(transport);
let failed = 0;
for (const file of process.argv.slice(2)) {
  const answer = await client.callTool({ name: "check_compliance", arguments: { path: resolve(file) } });
  const text = answer.content?.map((part) => part.text ?? "").join("") ?? "";
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (answer.isError) failed += 1;
  console.log(JSON.stringify({ file, error: Boolean(answer.isError), result: data }));
}
await client.close();
process.exitCode = failed ? 1 : 0;
