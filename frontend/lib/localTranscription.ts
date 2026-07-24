// Fallback voice input path for browsers where native SpeechRecognition doesn't work (Brave, as
// of a currently-open upstream bug - see speech.ts) or doesn't exist at all (Firefox, Safari).
// Records real microphone audio via getUserMedia/MediaRecorder - that part isn't affected by
// Brave's broken speech-recognition *service*, only the recognition step is - then transcribes
// it locally with a small Whisper model running in a Web Worker (whisperWorker.ts). Nothing
// leaves the browser: no server call, no API key.

export interface AudioRecorderHandle {
  stop: () => Promise<Float32Array>;
  cancel: () => void;
}

export async function startAudioRecording(): Promise<AudioRecorderHandle> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const chunks: Blob[] = [];
  const recorder = new MediaRecorder(stream);
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };

  const stopped = new Promise<void>((resolve) => {
    recorder.onstop = () => resolve();
  });

  recorder.start();
  const releaseStream = () => stream.getTracks().forEach((track) => track.stop());

  return {
    stop: async () => {
      recorder.stop();
      await stopped;
      releaseStream();
      const blob = new Blob(chunks, { type: recorder.mimeType });
      return decodeToWhisperSamples(blob);
    },
    cancel: () => {
      recorder.stop();
      releaseStream();
    },
  };
}

// Whisper expects 16kHz mono float32 PCM - MediaRecorder outputs a compressed container
// (webm/opus, format varies by browser), so this decodes it with the browser's own codec support
// and resamples via OfflineAudioContext (which also downmixes to mono for free when the
// destination has fewer channels than the source - standard Web Audio channel interpretation).
async function decodeToWhisperSamples(blob: Blob): Promise<Float32Array> {
  const arrayBuffer = await blob.arrayBuffer();
  const audioContext = new AudioContext();
  try {
    const decoded = await audioContext.decodeAudioData(arrayBuffer);
    const targetSampleRate = 16000;
    const offlineContext = new OfflineAudioContext(
      1,
      Math.ceil(decoded.duration * targetSampleRate),
      targetSampleRate
    );
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

type WorkerMessage =
  | { status: "progress"; progress: unknown }
  | { status: "ready" }
  | { status: "complete"; text: string }
  | { status: "error"; error: string };

let worker: Worker | null = null;

function getWorker(): Worker {
  worker ??= new Worker(new URL("./whisperWorker.ts", import.meta.url), { type: "module" });
  return worker;
}

export function transcribeAudio(samples: Float32Array, onStatus?: (status: string) => void): Promise<string> {
  return new Promise((resolve, reject) => {
    const w = getWorker();

    const handleMessage = (event: MessageEvent<WorkerMessage>) => {
      const data = event.data;
      if (data.status === "progress") {
        onStatus?.("Downloading speech model (one-time, ~40MB)...");
      } else if (data.status === "ready") {
        onStatus?.("Transcribing...");
      } else if (data.status === "complete") {
        w.removeEventListener("message", handleMessage);
        resolve(data.text);
      } else if (data.status === "error") {
        w.removeEventListener("message", handleMessage);
        reject(new Error(data.error));
      }
    };

    w.addEventListener("message", handleMessage);
    w.postMessage({ audio: samples });
  });
}
