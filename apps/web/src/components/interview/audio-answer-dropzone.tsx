"use client";

import { cn } from "cn";
import { FileAudio, Mic } from "lucide-react";
import { useState } from "react";

import { AUDIO_EXTENSIONS, MAX_AUDIO_BYTES } from "@/lib/candidate-api";

const ACCEPT = "audio/*,.m4a,.mp3,.wav,.webm,.ogg,.mp4";

interface AudioAnswerDropzoneProps {
  id: string;
  file: File | null;
  onSelect: (file: File) => void;
  onRemove: () => void;
  disabled?: boolean;
}

function formatSize(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function AudioAnswerDropzone({
  id,
  file,
  onSelect,
  onRemove,
  disabled,
}: AudioAnswerDropzoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const acceptFile = (candidate: File | undefined) => {
    if (!candidate || disabled) return;
    const ext = candidate.name
      .slice(candidate.name.lastIndexOf("."))
      .toLowerCase();
    if (!(AUDIO_EXTENSIONS as readonly string[]).includes(ext)) {
      setError(
        "That file type isn't supported. Please use MP3, M4A, WAV, WebM, OGG or MP4.",
      );
      return;
    }
    if (candidate.size === 0) {
      setError("Please choose an audio file before submitting.");
      return;
    }
    if (candidate.size > MAX_AUDIO_BYTES) {
      setError(
        "That file is larger than 25 MB. Please upload a shorter recording.",
      );
      return;
    }
    setError(null);
    onSelect(candidate);
  };

  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor={id}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          // Drag-drop of multiple files: take the first, ignore the rest.
          acceptFile(e.dataTransfer.files[0]);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-2.5 rounded-xl border-2 border-primary-muted border-dashed bg-dropzone px-5 py-9 text-center focus-within:border-primary focus-within:outline-2 focus-within:outline-primary focus-within:outline-offset-1",
          dragOver && "border-primary bg-primary-soft",
          disabled && "pointer-events-none opacity-50",
        )}
      >
        <span className="flex size-12 items-center justify-center rounded-full bg-primary-subtle">
          <Mic className="size-5.5 text-primary-strong" aria-hidden />
        </span>
        <span className="font-semibold text-body">
          Drop an audio file or{" "}
          <span className="text-primary-strong">browse</span>
        </span>
        <span className="text-meta text-muted-foreground">
          MP3, M4A, WAV or WebM · up to 25 MB
        </span>
        <input
          id={id}
          type="file"
          accept={ACCEPT}
          disabled={disabled}
          className="sr-only"
          onChange={(e) => {
            acceptFile(e.target.files?.[0]);
            // Reset so picking the same file twice still fires onChange.
            e.target.value = "";
          }}
        />
      </label>

      {file && (
        <div className="flex items-center justify-between gap-3 rounded-lg border bg-card px-4 py-3">
          <div className="flex min-w-0 items-center gap-2 text-body-sm">
            <FileAudio
              className="size-4 shrink-0 text-primary-strong"
              aria-hidden
            />
            <span className="truncate">{file.name}</span>
            <span className="shrink-0 text-meta text-muted-foreground">
              {formatSize(file.size)}
            </span>
          </div>
          <button
            type="button"
            onClick={onRemove}
            disabled={disabled}
            className="shrink-0 font-medium text-body-sm text-primary-strong hover:text-primary-deep"
          >
            Remove
          </button>
        </div>
      )}

      {error && <p className="text-danger-ink text-meta">{error}</p>}
    </div>
  );
}
