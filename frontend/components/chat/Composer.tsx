"use client";

import { ArrowUp, ImagePlus, Mic, Square, X } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";

import { uploadAttachment } from "@/lib/api/attachments";
import { startAudioRecording, transcribeAudio, type AudioRecorderHandle } from "@/lib/localTranscription";
import { describeSpeechError, startSpeechRecognition, type RecognitionHandle } from "@/lib/speech";

type VoiceMode = "idle" | "native" | "recording" | "transcribing";

interface PendingAttachment {
  id: string;
  previewUrl: string;
  filename: string;
}

export function Composer({
  onSend,
  onStop,
  disabled,
}: {
  onSend: (content: string, attachmentIds: string[]) => void;
  onStop: () => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");
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
    } catch {
      setSpeechError("Local transcription failed.");
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
    } catch {
      setVoiceMode("idle");
      setVoiceStatus(null);
      setSpeechError("Microphone access failed.");
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
          return { id: attachment.id, previewUrl: URL.createObjectURL(file), filename: attachment.filename };
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
    onSend(trimmed, pending.map((p) => p.id));
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
        <div className="rounded-[28px] border border-black/10 dark:border-white/15 bg-white dark:bg-neutral-800 shadow-sm px-4 py-2.5">
          {pending.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {pending.map((p) => (
                <div key={p.id} className="group relative">
                  {/* eslint-disable-next-line @next/next/no-img-element -- local object URL preview */}
                  <img src={p.previewUrl} alt={p.filename} className="h-16 w-16 rounded-lg object-cover" />
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
              accept="image/png,image/jpeg,image/webp,image/gif"
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled || isUploading}
              aria-label="Attach image"
              className="flex-shrink-0 rounded-full p-2 text-black/50 hover:bg-black/5 disabled:opacity-40 dark:text-white/50 dark:hover:bg-white/10"
            >
              <ImagePlus size={19} />
            </button>
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
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              placeholder="Message..."
              rows={1}
              className="flex-1 resize-none bg-transparent py-1.5 text-[15px] outline-none disabled:opacity-50 placeholder:text-black/40 dark:placeholder:text-white/40 max-h-[200px]"
            />
            {disabled ? (
              <button
                onClick={onStop}
                className="flex-shrink-0 rounded-full bg-black dark:bg-white p-2 text-white dark:text-black"
                aria-label="Stop generating"
              >
                <Square size={15} fill="currentColor" />
              </button>
            ) : (
              <button
                onClick={submit}
                disabled={(!value.trim() && pending.length === 0) || isUploading}
                className="flex-shrink-0 rounded-full bg-black dark:bg-white p-2 text-white dark:text-black disabled:opacity-30"
                aria-label="Send message"
              >
                <ArrowUp size={17} />
              </button>
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
