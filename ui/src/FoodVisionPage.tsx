import React, { useState } from "react";

const API_BASE_URL = "http://localhost:8000";

type FoodVisionPageProps = {
  onBack: () => void;
};

export default function FoodVisionPage({ onBack }: FoodVisionPageProps) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
    setAnalysis("");
    setError("");
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(selected ? URL.createObjectURL(selected) : null);
  };

  const onAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || loading) return;
    setLoading(true);
    setError("");
    setAnalysis("");
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(`${API_BASE_URL}/api/v1/vision/analyze-food`, {
        method: "POST",
        body,
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `HTTP ${res.status}`);
      }
      const data = (await res.json()) as { analysis: string };
      setAnalysis(data.analysis || "No analysis returned.");
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center px-4 font-sans">
      <div className="w-full max-w-3xl bg-white rounded-3xl shadow-2xl overflow-hidden">
        <header className="h-16 border-b border-slate-200 flex items-center justify-between px-6">
          <div>
            <h1 className="text-lg font-bold text-slate-800">Food Vision (Gemini Flash)</h1>
            <p className="text-xs text-slate-500">Upload a meal photo for item / portion estimates</p>
          </div>
          <button
            type="button"
            onClick={onBack}
            className="text-xs font-medium text-slate-500 hover:text-emerald-600"
          >
            ← Back to Chat
          </button>
        </header>

        <div className="p-6 space-y-6">
          <form onSubmit={onAnalyze} className="space-y-4">
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase">Food image</span>
              <input
                type="file"
                accept="image/*"
                onChange={onFileChange}
                className="mt-2 block w-full text-sm text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-emerald-50 file:text-emerald-700 hover:file:bg-emerald-100"
              />
            </label>

            {previewUrl && (
              <div className="rounded-2xl overflow-hidden border border-slate-200 bg-slate-50">
                <img src={previewUrl} alt="Food preview" className="max-h-72 w-full object-contain" />
              </div>
            )}

            <button
              type="submit"
              disabled={!file || loading}
              className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-xl px-6 py-3 text-sm font-semibold"
            >
              {loading ? "Analyzing…" : "Analyze with Gemini"}
            </button>
          </form>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl p-4 whitespace-pre-wrap">
              {error}
            </div>
          )}

          {analysis && (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-3">Gemini analysis</h2>
              <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans leading-relaxed">
                {analysis}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
