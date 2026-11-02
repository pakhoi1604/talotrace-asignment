// Audio answer: meta line + native player + the honest "Transcription not
// built" label (rule 5 — the API returns bytes only, no transcript exists).
// The URL is the HR playback route; the cookie rides along same-origin.

import { Badge } from "@/components/ui/badge";
import type { AudioMeta } from "@/lib/api-types";
import { audioFormatLabel, formatBytes, formatTime } from "@/lib/hr-format";

interface AudioAnswerPlayerProps {
  audio: AudioMeta;
  receivedAt: string;
}

export function AudioAnswerPlayer({
  audio,
  receivedAt,
}: AudioAnswerPlayerProps) {
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-col gap-2 rounded-lg bg-muted p-3.5">
        <span className="font-semibold text-meta">
          Audio answer arrived · {audioFormatLabel(audio.content_type)} ·{" "}
          {formatBytes(audio.size_bytes)} · received {formatTime(receivedAt)}
        </span>
        {/* biome-ignore lint/a11y/useMediaCaption: no transcript exists — the "Transcription not built" badge states it */}
        <audio controls preload="none" src={audio.url} className="w-full" />
      </div>
      <div className="flex flex-col gap-1">
        <Badge variant="warning" className="self-start">
          Transcription not built
        </Badge>
        <span className="text-caption text-muted-foreground">
          Listen to score this answer manually (Override).
        </span>
      </div>
    </div>
  );
}
