import { getIcon } from "seti-icons";

export function getFileIcon(name: string): string {
  return getIcon(name).svg;
}

const languageMap: Record<string, string> = {
  ts: "typescript",
  tsx: "typescript",
  js: "javascript",
  jsx: "javascript",
  py: "python",
  json: "json",
  md: "markdown",
  css: "css",
  scss: "scss",
  html: "html",
  yml: "yaml",
  yaml: "yaml",
  toml: "toml",
  sql: "sql",
  sh: "shell",
  dockerfile: "dockerfile",
  xml: "xml",
  svg: "xml",
  txt: "plaintext",
};

export function getLanguage(filename: string): string {
  const lower = filename.toLowerCase();
  if (lower === "dockerfile") return "dockerfile";

  const dotIndex = lower.lastIndexOf(".");
  if (dotIndex === -1) return "plaintext";

  const ext = lower.slice(dotIndex + 1);
  return languageMap[ext] ?? "plaintext";
}
