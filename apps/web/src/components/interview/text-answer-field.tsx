import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { MAX_TEXT_CHARS } from "@/lib/candidate-api";

interface TextAnswerFieldProps {
  id: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function TextAnswerField({
  id,
  value,
  onChange,
  disabled,
}: TextAnswerFieldProps) {
  const overLimit = value.length > MAX_TEXT_CHARS;

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id} className="font-medium text-body-sm">
        Your answer
      </Label>
      <Textarea
        id={id}
        rows={9}
        placeholder="Write your answer here…"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        aria-invalid={overLimit || undefined}
      />
      <span className="text-meta text-muted-foreground">
        Draft saved on this device
      </span>
      {overLimit && (
        <span className="text-danger-ink text-meta">
          Your answer is too long. Please keep it under 10,000 characters.
        </span>
      )}
    </div>
  );
}
