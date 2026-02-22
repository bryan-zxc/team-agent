type FileIconInfo = {
  label: string;
  colour: string;
};

const extensionMap: Record<string, FileIconInfo> = {
  ts: { label: "TS", colour: "#3178C6" },
  tsx: { label: "TX", colour: "#3178C6" },
  js: { label: "JS", colour: "#F0DB4F" },
  jsx: { label: "JX", colour: "#F0DB4F" },
  py: { label: "PY", colour: "#3776AB" },
  json: { label: "{}", colour: "#C4956A" },
  md: { label: "MD", colour: "#8E8983" },
  css: { label: "CS", colour: "#9B59B6" },
  scss: { label: "SC", colour: "#CD6799" },
  html: { label: "<>", colour: "#E34C26" },
  yml: { label: "YM", colour: "#CB171E" },
  yaml: { label: "YM", colour: "#CB171E" },
  toml: { label: "TM", colour: "#9C4121" },
  sql: { label: "SQ", colour: "#336791" },
  sh: { label: "SH", colour: "#4EAA25" },
  dockerfile: { label: "DK", colour: "#2496ED" },
  gitignore: { label: "GI", colour: "#F05032" },
  env: { label: "EN", colour: "#ECD53F" },
  lock: { label: "LK", colour: "#8E8983" },
  svg: { label: "SV", colour: "#FFB13B" },
  png: { label: "PN", colour: "#8E8983" },
  jpg: { label: "JP", colour: "#8E8983" },
  txt: { label: "TX", colour: "#8E8983" },
};

const defaultFile: FileIconInfo = { label: "F", colour: "var(--text-muted)" };
const folderInfo: FileIconInfo = { label: "", colour: "var(--accent)" };

export function getFileIcon(name: string, isDirectory: boolean): FileIconInfo {
  if (isDirectory) return folderInfo;

  const dotIndex = name.lastIndexOf(".");
  if (dotIndex === -1) {
    const lower = name.toLowerCase();
    if (lower === "dockerfile") return extensionMap.dockerfile;
    if (lower === ".gitignore") return extensionMap.gitignore;
    if (lower === ".env") return extensionMap.env;
    return defaultFile;
  }

  const ext = name.slice(dotIndex + 1).toLowerCase();
  return extensionMap[ext] ?? defaultFile;
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
