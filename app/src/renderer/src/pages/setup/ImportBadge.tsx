import { Badge } from "@/components/ui/Badge";

export type ImportInfo = { imported: Set<string>; missing: Set<string> };

export function ImportBadge({ field, info }: { field: string; info: ImportInfo | null }) {
  if (!info) return null;
  if (info.imported.has(field)) return <Badge tone="accent">Imported</Badge>;
  if (info.missing.has(field)) return <Badge tone="warn">Not found — enter manually</Badge>;
  return null;
}
