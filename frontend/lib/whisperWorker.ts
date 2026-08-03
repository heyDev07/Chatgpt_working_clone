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
    // Explicit dtype, not the library default: the default WASM dtype ("q8") still resolves to a
    // 4-bit block-quantized (q4) variant for this model's decoder embed_tokens weights, and the
    // onnxruntime-web build here can't execute that op (MatMulNBits) - reproduced live as
    // "Missing required scale ... weight_transposed_DequantizeLinear". fp32 sidesteps every
    // quantization-kernel compatibility question entirely - whisper-tiny.en is small enough
    // (~150MB instead of ~40MB) that the larger one-time download is worth trading for actually
    // working across browsers.
    transcriberPromise = pipeline("automatic-speech-recognition", MODEL_ID, { progress_callback, dtype: "fp32" });
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
