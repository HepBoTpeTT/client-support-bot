export function parseServerDate(value?: string | null): Date | null {
  if (!value) return null;

  const normalized =
    /[zZ]$|[+-]\d{2}:\d{2}$/.test(value)
      ? value
      : `${value}Z`;

  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatServerDate(value?: string | null): string {
  const date = parseServerDate(value);
  if (!date) return value ?? "";

  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}