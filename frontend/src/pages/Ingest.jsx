import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

export default function Ingest() {
  const [mode, setMode] = useState("paste"); // paste | upload
  const [text, setText] = useState("");
  const [sourceType, setSourceType] = useState("note");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef();
  const navigate = useNavigate();

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      let entry;
      if (mode === "paste") {
        if (!text.trim()) { setError("Text is required."); return; }
        entry = await api.entries.create(text, sourceType);
      } else {
        if (!file) { setError("Choose a file."); return; }
        entry = await api.entries.upload(file, sourceType);
      }
      navigate(`/entry/${entry.id}`);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold mb-6">Add entry</h1>

      <div className="flex gap-1 mb-6 bg-neutral-900 rounded-lg p-1 w-fit">
        {["paste", "upload"].map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
              mode === m ? "bg-neutral-700 text-white" : "text-neutral-400 hover:text-neutral-200"
            }`}
          >
            {m === "paste" ? "Paste text" : "Upload .txt"}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="block text-xs text-neutral-400 mb-1.5">Source type</label>
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
            className="text-sm bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-neutral-300 focus:outline-none focus:border-neutral-500"
          >
            <option value="note">Note</option>
            <option value="transcript">Transcript</option>
          </select>
        </div>

        {mode === "paste" ? (
          <div>
            <label className="block text-xs text-neutral-400 mb-1.5">Text</label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={12}
              placeholder="Paste your note or transcript here..."
              className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-neutral-500 resize-y"
            />
          </div>
        ) : (
          <div>
            <label className="block text-xs text-neutral-400 mb-1.5">File (.txt)</label>
            <input
              ref={fileRef}
              type="file"
              accept=".txt,text/plain"
              onChange={(e) => setFile(e.target.files[0])}
              className="text-sm text-neutral-400 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-neutral-700 file:text-neutral-200 file:text-sm file:cursor-pointer hover:file:bg-neutral-600"
            />
            {file && <p className="mt-1 text-xs text-neutral-500">{file.name}</p>}
          </div>
        )}

        {error && <p className="text-xs text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="px-5 py-2 bg-white text-neutral-950 rounded text-sm font-medium hover:bg-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Processing..." : "Save entry"}
        </button>

        {loading && (
          <p className="text-xs text-neutral-500">
            Claude is reading your text — this takes a few seconds.
          </p>
        )}
      </form>
    </div>
  );
}
