"use client";

import { ArrowUp, AudioLines, ChevronDown, FileText, ImagePlus, Mic, Square, X } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";

import { Tooltip } from "@/components/ui/Tooltip";
import { uploadAttachment } from "@/lib/api/attachments";
import { COMPOSER_MODES, type ComposerMode } from "@/lib/composerMode";
import { startAudioRecording, transcribeAudio, type AudioRecorderHandle } from "@/lib/localTranscription";
import { describeSpeechError, startSpeechRecognition, type RecognitionHandle } from "@/lib/speech";

type VoiceMode = "idle" | "native" | "recording" | "transcribing";

const MODE_PLACEHOLDERS: Record<ComposerMode, string> = {
  auto: "Message...",
  coding: "Describe what to build...",
  writing: "What should I write?",
  search: "Search the web...",
  agent: "Describe a multi-part request...",
  job_application: "What job are you looking for?",
  research: "What do you want researched?",
};

interface PendingAttachment {
  id: string;
  previewUrl: string;
  filename: string;
  contentType: string;
}

export function Composer({
  onSend,
  onStop,
  disabled,
  mode,
  onModeChange,
  onOpenVoiceMode,
}: {
  onSend: (content: string, attachmentIds: string[], mode: ComposerMode) => void;
  onStop: () => void;
  disabled?: boolean;
  // Owned by the parent, not this component - Composer gets unmounted and remounted as the
  // conversation transitions between layout states (see ChatWindow's empty-state vs.
  // has-messages branches), which would otherwise silently reset the selection to "auto" mid-use.
  mode: ComposerMode;
  onModeChange: (mode: ComposerMode) => void;
  // Opens VoiceModeOverlay (owned by ChatWindow, not here - see that component's docstring for
  // why voice mode is a separate, self-contained loop rather than living in this composer).
  onOpenVoiceMode?: () => void;
}) {
  const [value, setValue] = useState("");
  const [isModeMenuOpen, setIsModeMenuOpen] = useState(false);
  const [pending, setPending] = useState<PendingAttachment[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [voiceMode, setVoiceMode] = useState<VoiceMode>("idle");
  const [voiceStatus, setVoiceStatus] = useState<string | null>(null);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<RecognitionHandle | null>(null);
  const localRecordingRef = useRef<AudioRecorderHandle | null>(null);
  // The textarea's content at the moment listening started - interim speech results replace
  // only what's been said *this* listening session, appended after whatever was already typed,
  // rather than each new interim result overwriting the whole field.
  const baseValueRef = useRef("");

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  // Revoke any preview URLs still outstanding when the composer unmounts (e.g. navigating away
  // mid-upload) - otherwise those object URLs leak for the life of the tab.
  useEffect(() => {
    return () => {
      pending.forEach((p) => URL.revokeObjectURL(p.previewUrl));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- unmount-only cleanup
  }, []);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      localRecordingRef.current?.cancel();
    };
  }, []);

  const appendTranscript = (transcript: string, isFinal: boolean) => {
    const base = baseValueRef.current;
    const joined = base && !base.endsWith(" ") ? `${base} ${transcript}` : `${base}${transcript}`;
    setValue(joined);
    if (isFinal) baseValueRef.current = joined;
  };

  // Local (in-browser Whisper) recording, stopped: decode + transcribe, then insert the result.
  // Split out from toggleMic because it's also the path native voice input falls back into.
  const finishLocalRecording = async () => {
    const handle = localRecordingRef.current;
    localRecordingRef.current = null;
    if (!handle) {
      setVoiceMode("idle");
      return;
    }
    setVoiceMode("transcribing");
    setVoiceStatus("Transcribing...");
    try {
      const samples = await handle.stop();
      const text = await transcribeAudio(samples, setVoiceStatus);
      if (text.trim()) appendTranscript(text.trim(), true);
    } catch (err) {
      // Logged, not swallowed - this used to just show "Local transcription failed." with no
      // way to tell whether the mic decode, the ~40MB model download, or the Whisper pipeline
      // itself was what actually broke, which made a real report of this error undiagnosable.
      console.error("Local transcription failed:", err);
      const detail = err instanceof Error ? err.message : String(err);
      setSpeechError(`Local transcription failed: ${detail}`);
    } finally {
      setVoiceStatus(null);
      setVoiceMode("idle");
    }
  };

  const startLocalRecording = async () => {
    try {
      localRecordingRef.current = await startAudioRecording();
      setVoiceMode("recording");
      setVoiceStatus("Recording - click the mic again to stop and transcribe");
    } catch (err) {
      console.error("Microphone access failed:", err);
      setVoiceMode("idle");
      setVoiceStatus(null);
      const detail = err instanceof Error ? err.message : String(err);
      setSpeechError(`Microphone access failed: ${detail}`);
    }
  };

  const toggleMic = () => {
    if (voiceMode === "native") {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      setVoiceMode("idle");
      return;
    }
    if (voiceMode === "recording") {
      void finishLocalRecording();
      return;
    }
    if (voiceMode === "transcribing") {
      return; // ignore clicks while a transcription is already in flight
    }

    // idle -> try native speech recognition first (real-time, better UX where it actually works)
    setSpeechError(null);
    setVoiceStatus(null);
    baseValueRef.current = value;
    const handle = startSpeechRecognition(
      appendTranscript,
      () => {
        recognitionRef.current = null;
        setVoiceMode((mode) => (mode === "native" ? "idle" : mode));
      },
      (error) => {
        recognitionRef.current = null;
        if (error === "network" || error === "service-not-allowed") {
          // The mic itself isn't the problem here, only the recognition *service* is (this is
          // exactly the still-open Brave bug describeSpeechError documents) - local recording
          // doesn't depend on that service at all, so it's worth trying automatically rather
          // than just dead-ending on an error the user can't do anything about.
          setVoiceStatus("Native voice input unavailable - falling back to offline speech recognition...");
          void startLocalRecording();
        } else {
          setVoiceMode("idle");
          setSpeechError(describeSpeechError(error));
        }
      }
    );
    if (handle) {
      recognitionRef.current = handle;
      setVoiceMode("native");
    } else {
      // No SpeechRecognition constructor at all (Firefox, Safari) - go straight to local.
      void startLocalRecording();
    }
  };

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    e.target.value = ""; // allow re-selecting the same file later
    if (!files.length) return;

    setIsUploading(true);
    try {
      const uploaded = await Promise.all(
        files.map(async (file) => {
          const attachment = await uploadAttachment(file);
          return {
            id: attachment.id,
            previewUrl: URL.createObjectURL(file),
            filename: attachment.filename,
            contentType: attachment.content_type,
          };
        })
      );
      setPending((prev) => [...prev, ...uploaded]);
    } catch {
      // Upload failures are rare (bad file type/size, network) and the file simply doesn't
      // appear in the preview strip - matches this composer's existing lack of granular
      // inline error UI elsewhere (e.g. send failures surface via ChatWindow's error banner).
    } finally {
      setIsUploading(false);
    }
  };

  const removeAttachment = (id: string) => {
    setPending((prev) => {
      const target = prev.find((p) => p.id === id);
      if (target) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((p) => p.id !== id);
    });
  };

  const submit = () => {
    const trimmed = value.trim();
    if ((!trimmed && pending.length === 0) || disabled || isUploading) return;
    onSend(trimmed, pending.map((p) => p.id), mode);
    setValue("");
    baseValueRef.current = ""; // keep in sync if voice input is still listening after send
    pending.forEach((p) => URL.revokeObjectURL(p.previewUrl));
    setPending([]);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="px-4 pb-6 pt-2">
      <div className="mx-auto max-w-3xl">
        {/* Explicit mode overrides - "auto" (default) leaves the existing classify-and-respond
            pipeline completely untouched; the other three are additive, not replacements. */}
        <div className="relative mb-1.5">
          <button
            onClick={() => setIsModeMenuOpen((prev) => !prev)}
            className="flex items-center gap-1 rounded-full bg-black/5 px-2.5 py-1 text-xs font-medium text-black/60 hover:bg-black/10 dark:bg-white/10 dark:text-white/60 dark:hover:bg-white/15"
          >
            {COMPOSER_MODES.find((m) => m.value === mode)?.label}
            <ChevronDown size={12} className={isModeMenuOpen ? "rotate-180 transition-transform" : "transition-transform"} />
          </button>
          {isModeMenuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setIsModeMenuOpen(false)} />
              <div className="absolute bottom-full left-0 z-50 mb-2 w-56 rounded-xl border border-black/10 bg-white p-1 shadow-lg dark:border-white/10 dark:bg-neutral-800">
                {COMPOSER_MODES.map((m) => (
                  <button
                    key={m.value}
                    onClick={() => {
                      onModeChange(m.value);
                      setIsModeMenuOpen(false);
                    }}
                    className={`flex w-full flex-col items-start rounded-lg px-2.5 py-1.5 text-left ${
                      mode === m.value
                        ? "bg-black/5 dark:bg-white/10"
                        : "hover:bg-black/5 dark:hover:bg-white/10"
                    }`}
                  >
                    <span className="text-sm font-medium text-black/80 dark:text-white/80">{m.label}</span>
                    <span className="text-xs text-black/40 dark:text-white/40">{m.description}</span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
        <div className="rounded-[28px] border border-black/10 dark:border-white/15 bg-white dark:bg-neutral-800 shadow-sm px-4 py-2.5">
          {pending.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {pending.map((p) => (
                <div key={p.id} className="group relative">
                  {p.contentType.startsWith("image/") ? (
                    // eslint-disable-next-line @next/next/no-img-element -- local object URL preview
                    <img src={p.previewUrl} alt={p.filename} className="h-16 w-16 rounded-lg object-cover" />
                  ) : (
                    // Uses the local blob URL from file-select directly rather than AttachmentFile
                    // (which re-fetches by id) - we already have the bytes right here, no need for
                    // a round-trip before the message is even sent.
                    <a
                      href={p.previewUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex h-16 max-w-[160px] items-center gap-2 rounded-lg border border-black/10 bg-black/5 px-3 text-sm text-black/70 dark:border-white/10 dark:bg-white/5 dark:text-white/70"
                    >
                      <FileText size={16} className="flex-shrink-0" />
                      <span className="truncate">{p.filename}</span>
                    </a>
                  )}
                  <button
                    onClick={() => removeAttachment(p.id)}
                    aria-label={`Remove ${p.filename}`}
                    className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-black text-white opacity-0 group-hover:opacity-100 dark:bg-white dark:text-black"
                  >
                    <X size={11} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="flex items-end gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif,.pdf,.docx,.txt,.csv,.xlsx"
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />
            <Tooltip label="Add photos or files">
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled || isUploading}
                aria-label="Attach image or document"
                className="flex-shrink-0 rounded-full p-2 text-black/50 hover:bg-black/5 disabled:opacity-40 dark:text-white/50 dark:hover:bg-white/10"
              >
                <ImagePlus size={19} />
              </button>
            </Tooltip>
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              placeholder={MODE_PLACEHOLDERS[mode]}
              rows={1}
              className="flex-1 resize-none bg-transparent py-1.5 text-[15px] outline-none disabled:opacity-50 placeholder:text-black/40 dark:placeholder:text-white/40 max-h-[200px]"
            />
            {/* Mic grouped with Send at the trailing end, matching ChatGPT's composer layout -
                previously sat right after the attach button on the leading side instead. */}
            <Tooltip label={voiceMode === "idle" ? "Dictate" : "Stop dictating"}>
              <button
                onClick={toggleMic}
                disabled={disabled || voiceMode === "transcribing"}
                aria-label={voiceMode === "idle" ? "Start voice input" : "Stop voice input"}
                className={`flex-shrink-0 rounded-full p-2 disabled:opacity-40 ${
                  voiceMode === "native" || voiceMode === "recording"
                    ? "text-red-500 hover:bg-red-500/10 animate-pulse"
                    : "text-black/50 hover:bg-black/5 dark:text-white/50 dark:hover:bg-white/10"
                }`}
              >
                <Mic size={19} />
              </button>
            </Tooltip>
            {onOpenVoiceMode && (
              <Tooltip label="Voice mode">
                <button
                  onClick={onOpenVoiceMode}
                  disabled={disabled}
                  aria-label="Open voice mode"
                  className="flex-shrink-0 rounded-full p-2 text-black/50 hover:bg-black/5 disabled:opacity-40 dark:text-white/50 dark:hover:bg-white/10"
                >
                  <AudioLines size={19} />
                </button>
              </Tooltip>
            )}
            {disabled ? (
              <Tooltip label="Stop generating">
                <button
                  onClick={onStop}
                  className="flex-shrink-0 rounded-full bg-black dark:bg-white p-2 text-white dark:text-black"
                  aria-label="Stop generating"
                >
                  <Square size={15} fill="currentColor" />
                </button>
              </Tooltip>
            ) : (
              <Tooltip label="Send">
                <button
                  onClick={submit}
                  disabled={(!value.trim() && pending.length === 0) || isUploading}
                  className="flex-shrink-0 rounded-full bg-black dark:bg-white p-2 text-white dark:text-black disabled:opacity-30"
                  aria-label="Send message"
                >
                  <ArrowUp size={17} />
                </button>
              </Tooltip>
            )}
          </div>
        </div>
        {speechError && (
          <p className="mt-2 text-center text-xs text-red-500">{speechError}</p>
        )}
        {voiceStatus && !speechError && (
          <p className="mt-2 text-center text-xs text-black/40 dark:text-white/40">{voiceStatus}</p>
        )}
        <p className="mt-2 text-center text-xs text-black/30 dark:text-white/30">
          AI can make mistakes. Check important info.
        </p>
      </div>
    </div>
  );
}
