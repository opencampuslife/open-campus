import path from "node:path";

export class Sandbox {
  static readonly ALLOWED_PREFIXES = ["data/ingestion", "knowledge_vault"];

  static validate(requestedPath: string, projectRoot: string): boolean {
    const resolved = path.resolve(projectRoot, requestedPath);
    for (const prefix of this.ALLOWED_PREFIXES) {
      const allowedPath = path.resolve(projectRoot, prefix);
      if (resolved.startsWith(allowedPath + path.sep) || resolved === allowedPath) {
        return true;
      }
    }
    return false;
  }

  static resolve(relativePath: string, projectRoot: string): string {
    return path.resolve(projectRoot, relativePath);
  }

  static listAllowed(projectRoot: string): string[] {
    return this.ALLOWED_PREFIXES.map(p => path.resolve(projectRoot, p));
  }
}
