import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface ColorFieldProps {
  label: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
}

export function ColorField({
  label,
  value,
  placeholder,
  onChange,
}: ColorFieldProps) {
  const safeColor =
    /^#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})$/.test(value || "")
      ? value
      : placeholder;

  return (
    <div className="flex flex-col gap-1">
      <Label className="text-sm text-muted-foreground">{label}</Label>

      <div className="flex items-center gap-2">
        <input
          type="color"
          value={safeColor}
          onChange={(e) => onChange(e.target.value)}
          className="w-10 h-10 rounded cursor-pointer border border-border bg-transparent"
        />

        <Input
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-36 bg-muted border-border text-foreground"
        />
      </div>
    </div>
  );
}