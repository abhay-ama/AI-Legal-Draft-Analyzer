import React, { useState } from "react";

export default function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [corrected, setCorrected] = useState("");

  const handleUpload = (e) => setFile(e.target.files[0]);

  const analyzeDraft = async () => {
    if (!file) return;
    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      setResults(data.data);
      setCorrected(data.data.questions.join("\n"));
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const sendFeedback = async () => {
    if (!results) return;
    const formData = new FormData();
    formData.append("draft_text", results.draft_text);
    formData.append("predicted", results.questions.join("\n"));
    formData.append("corrected", corrected);
    await fetch("http://localhost:8000/feedback", {
      method: "POST",
      body: formData,
    });
    alert("Feedback submitted. Thanks for improving the AI!");
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center p-6 space-y-6">
      <h1 className="text-2xl font-bold">AI Legal Draft Analyzer (Self-Learning)</h1>
      <input type="file" onChange={handleUpload} />
      <button onClick={analyzeDraft} disabled={!file || loading}>
        {loading ? "Analyzing..." : "Analyze Draft"}
      </button>
      {results && (
        <div>
          <h2>Extracted Legal Questions</h2>
          <textarea value={corrected} onChange={(e) => setCorrected(e.target.value)} rows={6} cols={80} />
          <button onClick={sendFeedback} className="mt-2">Submit Feedback</button>
          <h2>Suggested Case Laws</h2>
          {results.cases.map((c, i) => (
            <div key={i}>
              <h3>Issue: {c.issue}</h3>
              <ul>
                {c.cases.map((cs, j) => (
                  <li key={j}><strong>{cs.name}</strong> ({cs.citation}): {cs.fragment}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
