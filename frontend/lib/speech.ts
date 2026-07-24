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

// The raw error codes (https://developer.mozilla.org/docs/Web/API/SpeechRecognitionErrorEvent/error)
// are accurate but not self-explanatory. "network" in particular is what Brave reports - as of a
// still-open Brave bug (github.com/brave/brave-browser/issues/55414, filed May 2026), its
// on-device speech recognition hangs indefinitely in a "downloading" state that never resolves,
// so the legacy webkitSpeechRecognition path falls through to this error. Not a settings fix -
// genuinely broken upstream in Brave right now, not something this app (or the user) can work
// around from privacy settings.
export function describeSpeechError(error: string): string {
  switch (error) {
    case "not-allowed":
    case "permission-denied":
      return "Microphone access was denied. Allow microphone access for this site and try again.";
    case "service-not-allowed":
      return "This browser's speech recognition service is disabled or unavailable. Try Chrome or Edge.";
    case "network":
      return "Voice input isn't working in this browser right now - this is a known, currently " +
        "unresolved bug in Brave's speech recognition (not something fixable via settings). " +
        "Use Chrome or Edge for voice input instead.";
    case "no-speech":
      return "No speech was detected. Try again.";
    case "audio-capture":
      return "No microphone was found.";
    default:
      return `Voice input failed (${error}).`;
  }
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
