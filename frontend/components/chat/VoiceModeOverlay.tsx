"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Mic, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { stopGeneration } from "@/lib/api/messages";
import { streamMessage } from "@/lib/api/stream";
import { describeSpeechError } from "@/lib/speech";
import {
  popCompleteSentences,
  startContinuousLocalListening,
  startContinuousRecognition,
  SpeechQueue,
  type ContinuousListenHandle,
} from "@/lib/voiceMode";

type Phase = "listening" | "thinking" | "speaking";

// Full-screen overlay, not an extension of Composer.tsx's inline dictation button - this is a
// different UX (continuous conversation, auto-submit, spoken replies), not one-shot
// dictate-into-textbox, and it's simplest kept as its own self-contained loop rather than
// entangled with ChatWindow's text-mode rendering state (pendingMessages/streamingContent/etc):
// it drives streamMessage() directly and lets the existing onDone-triggered query invalidation
// bring the normal message list up to date once the user exits back to text mode.
export function VoiceModeOverlay({ conversationId, onClose }: { conversationId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<Phase>("listening");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const listenHandleRef = useRef<ContinuousListenHandle | null>(null);
  const speechQueueRef = useRef<SpeechQueue | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  // Mirrors `phase` for callbacks that close over stale state otherwise (started once, long
  // before the phase they need to check was set) - React state itself can't be read fresh from
  // inside a closure created on an earlier render.
  const phaseRef = useRef<Phase>("listening");
  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  const invalidateConversation = () => {
    queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
    queryClient.invalidateQueries({ queryKey: ["conversations"] });
  };

  const endCurrentTurn = () => {
    // Aborting the client fetch alone does not stop server-side generation - chat_service.py's
    // _stream_resilient deliberately keeps generating after a client disconnect, so an explicit
    // stop call is what actually halts it, same mechanism the normal "Stop generating" button
    // already uses. Best-effort: interruption should feel instant client-side regardless of
    // whether this call succeeds.
    void stopGeneration(conversationId).catch(() => {});
    abortControllerRef.current?.abort();
    speechQueueRef.current?.stop();
  };

  const handleFinalTranscript = (transcript: string) => {
    setInterimTranscript("");
    // Speaking over the assistant mid-reply is an interruption: tear down whatever's in flight
    // before starting the new turn. stop()/abort() run synchronously here, then setPhase("thinking")
    // runs right after in the same handler - with React 18's batching, that's the value that wins
    // for the next render even though the torn-down turn's own onSpeakingChange(false) callback
    // (fired synchronously inside speechQueueRef.current?.stop() above) also calls setPhase.
    if (phaseRef.current !== "listening") {
      endCurrentTurn();
    }

    setPhase("thinking");
    setErrorMessage(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;
    let streamDone = false;
    let sentenceBuffer = "";

    const queue = new SpeechQueue((isSpeaking) => {
      setPhase(isSpeaking ? "speaking" : streamDone ? "listening" : "thinking");
    });
    speechQueueRef.current = queue;

    void streamMessage(conversationId, transcript, {
      onToken: (delta) => {
        sentenceBuffer += delta;
        const { sentences, remainder } = popCompleteSentences(sentenceBuffer);
        sentenceBuffer = remainder;
        for (const sentence of sentences) queue.enqueue(sentence);
      },
      onDone: () => {
        streamDone = true;
        const trailing = sentenceBuffer.trim();
        sentenceBuffer = "";
        if (trailing) queue.enqueue(trailing);
        // If the queue has nothing left to play or fetch right now, it won't fire another
        // onSpeakingChange callback on its own (nothing changed) - without this, phase would
        // stay stuck on "thinking" forever whenever the reply ended with no trailing fragment
        // and everything before it had already finished playing.
        if (!queue.isActive) setPhase("listening");
        invalidateConversation();
      },
      onError: (message) => {
        streamDone = true;
        setErrorMessage(message);
        setPhase("listening");
      },
    }, controller.signal, [], undefined);
  };

  useEffect(() => {
    const handle = startContinuousRecognition(
      handleFinalTranscript,
      setInterimTranscript,
      // No native SpeechRecognition at all (Firefox, Safari) - fall back to the same on-device
      // Whisper path the existing dictation button uses, wrapped in basic silence-based
      // segmenting so it can approximate continuous listening too (see voiceMode.ts).
      () => {
        listenHandleRef.current = startContinuousLocalListening(handleFinalTranscript, (message) =>
          setErrorMessage(`Voice input failed: ${message}`)
        );
      },
      (error) => {
        if (error === "network" || error === "service-not-allowed") {
          listenHandleRef.current = startContinuousLocalListening(handleFinalTranscript, (message) =>
            setErrorMessage(`Voice input failed: ${message}`)
          );
        } else {
          setErrorMessage(describeSpeechError(error));
        }
      }
    );
    listenHandleRef.current = handle;

    return () => {
      listenHandleRef.current?.stop();
      abortControllerRef.current?.abort();
      speechQueueRef.current?.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- start-listening-once-on-mount, not per-render
  }, [conversationId]);

  const handleClose = () => {
    listenHandleRef.current?.stop();
    endCurrentTurn();
    onClose();
  };

  const statusText =
    phase === "listening"
      ? interimTranscript || "Listening..."
      : phase === "thinking"
        ? "Thinking..."
        : "Speaking - start talking to interrupt";

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-white dark:bg-neutral-900">
      <button
        onClick={handleClose}
        aria-label="Exit voice mode"
        className="absolute right-6 top-6 rounded-full p-2 text-black/50 hover:bg-black/5 dark:text-white/50 dark:hover:bg-white/10"
      >
        <X size={22} />
      </button>

      <div
        className={`flex h-32 w-32 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-violet-500 transition-transform ${
          phase === "speaking" ? "scale-110" : phase === "thinking" ? "animate-pulse" : ""
        }`}
      >
        <Mic size={40} className="text-white" />
      </div>

      <p className="mt-8 max-w-md px-6 text-center text-sm text-black/60 dark:text-white/60">{statusText}</p>

      {errorMessage && <p className="mt-3 max-w-md px-6 text-center text-xs text-red-500">{errorMessage}</p>}
    </div>
  );
}
