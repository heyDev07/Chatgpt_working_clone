// Thin wrapper around the browser's native Web Speech API - no backend/LLM call involved for
// either direction, so unlike every other Phase 10 slice this isn't affected by provider rate
// limits. Support is real but uneven (SpeechRecognition is Chrome/Edge via the webkit-prefixed
// constructor; Firefox and Safari don't implement it), so every entry point here is safe to call
// on an unsupported browser - it just no-ops instead of throwing.
//
// TypeScript's DOM lib doesn't ship SpeechRecognition itself (only its result/alternative
// sub-types) or the constructor's presence on Window, so the minimal surface this file needs is
// typed locally rather than via a global .d.ts augmentation.
interface SpeechRecognitionResultEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
}

interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechRecognitionResultEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | undefined {
  if (typeof window === "undefined") return undefined;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

export function isSpeechRecognitionSupported(): boolean {
  return !!getSpeechRecognitionConstructor();
}

export function isSpeechSynthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export interface RecognitionHandle {
  stop: () => void;
}

export function startSpeechRecognition(
  onResult: (transcript: string, isFinal: boolean) => void,
  onEnd: () => void,
  onError: (error: string) => void
): RecognitionHandle | null {
  const Ctor = getSpeechRecognitionConstructor();
  if (!Ctor) return null;

  const recognition = new Ctor();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-US";

  recognition.onresult = (event) => {
    // Only the segment starting at resultIndex is new this callback - results before it were
    // already reported (as interim or final) in a prior callback.
    let transcript = "";
    let isFinal = false;
    for (let i = event.resultIndex; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
      if (event.results[i].isFinal) isFinal = true;
    }
    onResult(transcript, isFinal);
  };
  recognition.onerror = (event) => onError(event.error);
  recognition.onend = onEnd;

  recognition.start();
  return { stop: () => recognition.stop() };
}

export function speakText(text: string, onEnd: () => void): void {
  if (!isSpeechSynthesisSupported()) {
    onEnd();
    return;
  }
  window.speechSynthesis.cancel(); // only one utterance should ever be in flight at a time
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.onend = onEnd;
  utterance.onerror = onEnd;
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking(): void {
  if (isSpeechSynthesisSupported()) window.speechSynthesis.cancel();
}
