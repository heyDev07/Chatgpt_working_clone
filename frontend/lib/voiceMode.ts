// Orchestration logic for live voice mode - composed on top of the existing speech.ts/
// localTranscription.ts primitives rather than modifying them, so the existing one-shot
// dictation button in Composer.tsx keeps behaving exactly as it does today. Two genuinely new
// capabilities live here: (1) turning those one-shot primitives into a continuous listening loop,
// and (2) speaking the assistant's reply sentence-by-sentence as it streams in, via the new /tts
// endpoint, instead of waiting for the full reply.

import { synthesizeSpeech } from "@/lib/api/tts";
import { startSpeechRecognition, type RecognitionHandle } from "@/lib/speech";
import { transcribeAudio } from "@/lib/localTranscription";

// --- Sentence chunking -----------------------------------------------------------------------

// Punctuation followed by whitespace/newline, i.e. *within* already-received text - deliberately
// does NOT match end-of-string, since during streaming the buffer is only a prefix of the
// eventual full reply and treating "what's arrived so far ends here" as a sentence boundary
// would cut sentences short. Whatever's left over once the stream finishes is handled by
// flushRemainder() below, not by this matching more eagerly.
const SENTENCE_BOUNDARY = /[.!?]+(?:\s+|\n+)/;

export function popCompleteSentences(buffer: string): { sentences: string[]; remainder: string } {
  const sentences: string[] = [];
  let remainder = buffer;
  let match = SENTENCE_BOUNDARY.exec(remainder);
  while (match) {
    const end = match.index + match[0].length;
    const candidate = remainder.slice(0, end).trim();
    remainder = remainder.slice(end);
    if (candidate) sentences.push(candidate);
    match = SENTENCE_BOUNDARY.exec(remainder);
  }
  return { sentences, remainder };
}

// --- Speech playback queue ---------------------------------------------------------------------

// One instance per assistant turn (created fresh, discarded after stop()/natural completion) -
// simpler than trying to reset internal state for reuse across turns, same reasoning a fresh
// AbortController is used per request rather than reused.
export class SpeechQueue {
  private pending: Promise<Blob | null>[] = [];
  private currentAudio: HTMLAudioElement | null = null;
  private stopped = false;
  private pumping = false;
  private onSpeakingChange?: (isSpeaking: boolean) => void;

  constructor(onSpeakingChange?: (isSpeaking: boolean) => void) {
    this.onSpeakingChange = onSpeakingChange;
  }

  // Fires the TTS request immediately (prefetching) rather than waiting for earlier sentences to
  // finish playing - this is what keeps playback gap-free instead of stuttering between sentences.
  enqueue(sentence: string): void {
    if (this.stopped) return;
    this.pending.push(synthesizeSpeech(sentence).catch(() => null));
    void this.pump();
  }

  private async pump(): Promise<void> {
    if (this.pumping) return;
    this.pumping = true;
    while (!this.stopped && this.pending.length > 0) {
      const next = this.pending.shift();
      if (!next) continue;
      const blob = await next;
      if (this.stopped || !blob) continue;
      await this.playBlob(blob);
    }
    this.pumping = false;
    if (!this.stopped) this.onSpeakingChange?.(false);
  }

  private playBlob(blob: Blob): Promise<void> {
    return new Promise((resolve) => {
      if (this.stopped) {
        resolve();
        return;
      }
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      this.currentAudio = audio;
      this.onSpeakingChange?.(true);
      const finish = () => {
        URL.revokeObjectURL(url);
        if (this.currentAudio === audio) this.currentAudio = null;
        resolve();
      };
      audio.onended = finish;
      audio.onerror = finish;
      void audio.play().catch(finish);
    });
  }

  // Interruption / turn end: drops anything queued or in-flight and stops whatever's audible
  // right now. Safe to call even if nothing is playing.
  stop(): void {
    this.stopped = true;
    this.pending = [];
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio.currentTime = 0;
      this.currentAudio = null;
    }
    this.onSpeakingChange?.(false);
  }

  get isSpeaking(): boolean {
    return this.currentAudio !== null;
  }

  // True while anything is queued, being synthesized, or playing - unlike isSpeaking, this stays
  // true during the gap between "enqueued" and "audio actually started", which is exactly the
  // window callers need to know about to avoid prematurely treating the queue as done.
  get isActive(): boolean {
    return this.pumping || this.currentAudio !== null || this.pending.length > 0;
  }
}

// --- Continuous listening: native SpeechRecognition path ---------------------------------------

export interface ContinuousListenHandle {
  stop: () => void;
}

// speech.ts's startSpeechRecognition already sets continuous=true, but browsers still end the
// underlying recognition session after a period of silence regardless - this wraps it with
// auto-restart on end, which is what actually makes listening continuous across an entire voice
// session rather than just across pauses within one utterance.
export function startContinuousRecognition(
  onFinalResult: (transcript: string) => void,
  onInterimResult: (transcript: string) => void,
  onUnsupported: () => void,
  onError: (error: string) => void
): ContinuousListenHandle {
  let handle: RecognitionHandle | null = null;
  let stopped = false;

  const begin = () => {
    if (stopped) return;
    handle = startSpeechRecognition(
      (transcript, isFinal) => {
        if (isFinal) {
          if (transcript.trim()) onFinalResult(transcript.trim());
        } else {
          onInterimResult(transcript);
        }
      },
      () => {
        handle = null;
        if (!stopped) begin();
      },
      (error) => {
        handle = null;
        if (stopped) return;
        if (error === "no-speech") {
          // Not a real error for a continuous session - browsers report this after a silent
          // stretch even though nothing is actually wrong. Just restart and keep listening.
          begin();
        } else {
          onError(error);
        }
      }
    );
    if (!handle) onUnsupported();
  };

  begin();

  return {
    stop: () => {
      stopped = true;
      handle?.stop();
      handle = null;
    },
  };
}

// --- Continuous listening: local Whisper fallback (no native SpeechRecognition) ----------------

// Whisper-tiny.en runs batch inference, not streaming - it has no notion of "continuous
// listening" on its own. This approximates it with simple energy-based silence detection (a
// single RMS-over-threshold check polled a few times a second, not a real VAD model): record
// until the mic has been quiet for SILENCE_MS after having heard speech, transcribe that segment,
// then start the next one. A deliberately simple heuristic, not a tuned/adaptive one.
const SILENCE_THRESHOLD = 0.01;
const SILENCE_MS = 1200;
const MAX_SEGMENT_MS = 15000;
const POLL_MS = 200;

export function startContinuousLocalListening(
  onSegment: (transcript: string) => void,
  onError: (message: string) => void
): ContinuousListenHandle {
  let stopped = false;
  let stream: MediaStream | null = null;

  const runSegment = async (): Promise<void> => {
    if (stopped) return;
    try {
      const recorderStream =
        stream ?? (stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true } }));
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(recorderStream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);

      const recorder = new MediaRecorder(recorderStream);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };
      const stoppedRecording = new Promise<void>((resolve) => {
        recorder.onstop = () => resolve();
      });
      recorder.start();

      let heardSpeech = false;
      let silenceStartedAt: number | null = null;
      const segmentStartedAt = Date.now();

      await new Promise<void>((resolve) => {
        const poll = () => {
          if (stopped || recorder.state !== "recording") {
            resolve();
            return;
          }
          analyser.getByteTimeDomainData(data);
          let sumSquares = 0;
          for (const sample of data) {
            const normalized = (sample - 128) / 128;
            sumSquares += normalized * normalized;
          }
          const rms = Math.sqrt(sumSquares / data.length);

          if (rms > SILENCE_THRESHOLD) {
            heardSpeech = true;
            silenceStartedAt = null;
          } else if (heardSpeech && silenceStartedAt === null) {
            silenceStartedAt = Date.now();
          }

          const elapsed = Date.now() - segmentStartedAt;
          const silentFor = silenceStartedAt ? Date.now() - silenceStartedAt : 0;
          if ((heardSpeech && silentFor > SILENCE_MS) || elapsed > MAX_SEGMENT_MS) {
            resolve();
          } else {
            setTimeout(poll, POLL_MS);
          }
        };
        poll();
      });

      recorder.stop();
      await stoppedRecording;
      await audioContext.close();

      if (heardSpeech && !stopped) {
        const blob = new Blob(chunks, { type: recorder.mimeType });
        const samples = await decodeForTranscription(blob);
        const text = await transcribeAudio(samples);
        if (text.trim() && !stopped) onSegment(text.trim());
      }
    } catch (err) {
      if (!stopped) onError(err instanceof Error ? err.message : String(err));
      return;
    }
    if (!stopped) void runSegment();
  };

  void runSegment();

  return {
    stop: () => {
      stopped = true;
      stream?.getTracks().forEach((track) => track.stop());
      stream = null;
    },
  };
}

// Duplicates localTranscription.ts's private decode step (16kHz mono resample) rather than
// exporting it from there - startAudioRecording() bundles recording + decoding into one
// stop()-triggered call, which doesn't fit this segment-by-segment loop's own recording/analysis
// setup above; only the decode math is actually shared.
async function decodeForTranscription(blob: Blob): Promise<Float32Array> {
  const arrayBuffer = await blob.arrayBuffer();
  const audioContext = new AudioContext();
  try {
    const decoded = await audioContext.decodeAudioData(arrayBuffer);
    const targetSampleRate = 16000;
    const offlineContext = new OfflineAudioContext(1, Math.ceil(decoded.duration * targetSampleRate), targetSampleRate);
    const source = offlineContext.createBufferSource();
    source.buffer = decoded;
    source.connect(offlineContext.destination);
    source.start();
    const rendered = await offlineContext.startRendering();
    return rendered.getChannelData(0);
  } finally {
    await audioContext.close();
  }
}
