// Runs entirely off the main thread: model download (~40MB, cached by the browser after the
// first use) and inference would otherwise freeze the UI for seconds at a time. Communicates
// with localTranscription.ts via postMessage only - this file has no knowledge of the composer,
// recording, or anything else, just "audio samples in, transcript text out".
import { pipeline, type AutomaticSpeechRecognitionPipeline, type ProgressCallback } from "@huggingface/transformers";

const MODEL_ID = "Xenova/whisper-tiny.en";

let transcriberPromise: Promise<AutomaticSpeechRecognitionPipeline> | null = null;

function getTranscriber(): Promise<AutomaticSpeechRecognitionPipeline> {
  if (!transcriberPromise) {
    const progress_callback: ProgressCallback = (progress) => {
      self.postMessage({ status: "progress", progress });
    };
    transcriberPromise = pipeline("automatic-speech-recognition", MODEL_ID, { progress_callback });
  }
  return transcriberPromise;
}

self.addEventListener("message", async (event: MessageEvent<{ audio: Float32Array }>) => {
  try {
    const transcriber = await getTranscriber();
    self.postMessage({ status: "ready" });
    const output = await transcriber(event.data.audio);
    const text = Array.isArray(output) ? output[0]?.text ?? "" : output.text;
    self.postMessage({ status: "complete", text });
  } catch (error) {
    self.postMessage({ status: "error", error: error instanceof Error ? error.message : String(error) });
  }
});
