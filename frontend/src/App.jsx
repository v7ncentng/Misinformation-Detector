import React, { useState } from "react";

// Simple icon components using SVG
const BrainIcon = () => (
  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
    <path d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zM11 8a1 1 0 012 0v4a1 1 0 11-2 0V8z"/>
  </svg>
);

const CheckIcon = () => (
  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
  </svg>
);

const XIcon = () => (
  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/>
  </svg>
);

const AlertIcon = () => (
  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
  </svg>
);

const EyeIcon = () => (
  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
    <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
    <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd"/>
  </svg>
);

const ChartIcon = () => (
  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
    <path d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zM8 7a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zM14 4a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z"/>
  </svg>
);

export default function App() {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [analysisHistory, setAnalysisHistory] = useState([]);

  const analyzeText = async () => {
    if (!text.trim()) return;
    
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      
      const data = await res.json();
      setResult(data);
      
      // Add to history
      setAnalysisHistory(prev => [
        { text: text.substring(0, 100) + "...", result: data, timestamp: new Date() },
        ...prev.slice(0, 4) // Keep last 5 analyses
      ]);
      
    } catch (error) {
      console.error("Error analyzing text:", error);
      if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
        setResult({ error: "Cannot connect to backend. Make sure it's running on http://localhost:8000" });
      } else {
        setResult({ error: `Analysis failed: ${error.message}` });
      }
    }
    setLoading(false);
  };

  const getRiskColor = (risk) => {
    switch (risk) {
      case "high": return "text-red-400 bg-red-900/30 border-red-500/30";
      case "medium": return "text-orange-400 bg-orange-900/30 border-orange-500/30";
      default: return "text-green-400 bg-green-900/30 border-green-500/30";
    }
  };

  const getClaimIcon = (claimType) => {
    switch (claimType) {
      case "factual_claim": return <CheckIcon />;
      case "potentially_false": return <XIcon />;
      case "unverified_claim": return <AlertIcon />;
      default: return <EyeIcon />;
    }
  };

  const sampleTexts = [
    "According to the World Health Organization, measles vaccination prevented an estimated 23 million deaths globally between 2000 and 2018.",
    "NASA reports that global average sea levels have risen about 8 inches since 1880.",
    "The CDC states that smoking increases the risk of lung cancer by 15 to 30 times compared to non-smokers.",
    "Studies on social media suggest that drinking bleach can cure viral infections instantly.",
    "I think pineapple is the best topping for pizza — it makes every bite sweet and savory.",
    "In my opinion, electric cars feel smoother and more enjoyable to drive than gas cars."
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-slate-900 to-black p-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="w-10 h-10 text-gray-400 flex items-center justify-center">
              🧠
            </div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-200 via-gray-300 to-white bg-clip-text text-transparent">
              AI Misinformation Spotter
            </h1>
          </div>
          <p className="text-gray-300 max-w-2xl mx-auto">
            Advanced AI-powered analysis to detect claims, assess credibility, and identify potential misinformation using multiple machine learning models.
          </p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Input Section */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-gray-900/50 backdrop-blur border border-gray-700/50 rounded-xl shadow-xl p-6">
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-white">
                <ChartIcon />
                Text Analysis
              </h2>
              
              <textarea
                className="w-full p-4 bg-gray-800/50 border border-gray-600/50 rounded-lg mb-4 focus:border-gray-400 focus:outline-none transition-colors text-white placeholder-gray-400 backdrop-blur"
                rows="6"
                placeholder="Enter text to analyze for potential misinformation, factual claims, or credibility assessment..."
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
              
              <div className="mb-4">
                <span className="text-sm text-gray-400 block mb-2">Try these examples:</span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {sampleTexts.map((sample, idx) => (
                    <button
                      key={idx}
                      onClick={() => setText(sample)}
                      className="text-xs bg-gray-800/50 border border-gray-600/30 text-gray-300 px-3 py-2 rounded-lg hover:bg-gray-700/50 hover:border-gray-500/50 transition-all text-left backdrop-blur"
                      title={sample}
                    >
                      {sample.substring(0, 50)}...
                    </button>
                  ))}
                </div>
              </div>
              
              <button
                onClick={analyzeText}
                disabled={loading || !text.trim()}
                className="bg-gradient-to-r from-gray-700 to-gray-600 hover:from-gray-600 hover:to-gray-500 text-white px-6 py-3 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2 font-semibold shadow-lg border border-gray-500/30"
              >
                <BrainIcon />
                {loading ? "Analyzing..." : "Analyze with AI"}
              </button>
            </div>

            {/* Results Section */}
            {result && (
              <div className="bg-gray-900/50 backdrop-blur border border-gray-700/50 rounded-xl shadow-xl p-6">
                {result.error ? (
                  <div className="flex items-center gap-3 text-red-400 bg-red-900/30 border border-red-500/30 p-4 rounded-lg backdrop-blur">
                    <XIcon />
                    <span className="font-medium">{result.error}</span>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Main Assessment */}
                    <div className="flex items-start gap-4">
                      <div className="text-gray-400 mt-1">
                        {getClaimIcon(result.claim_type)}
                      </div>
                      <div className="flex-1">
                        <h3 className="text-xl font-semibold mb-2 text-white">
                          {result.is_claim ? "Factual Claim Detected" : "No Factual Claims"}
                        </h3>
                        <p className="text-gray-300 mb-4">{result.explanation}</p>
                        
                        <div className="grid md:grid-cols-3 gap-4">
                          <div className="bg-gray-800/50 border border-gray-600/30 p-3 rounded-lg backdrop-blur">
                            <div className="text-sm text-gray-400">Confidence</div>
                            <div className="text-lg font-bold text-gray-300">
                              {(result.confidence * 100).toFixed(1)}%
                            </div>
                          </div>
                          <div className={`p-3 rounded-lg border backdrop-blur ${getRiskColor(result.risk_level)}`}>
                            <div className="text-sm opacity-75">Risk Level</div>
                            <div className="text-lg font-bold capitalize">
                              {result.risk_level}
                            </div>
                          </div>
                          <div className="bg-gray-800/50 border border-gray-600/30 p-3 rounded-lg backdrop-blur">
                            <div className="text-sm text-gray-400">Credibility</div>
                            <div className="text-lg font-bold text-gray-300 capitalize">
                              {result.credibility_assessment.replace('_', ' ')}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Analysis History */}
            {analysisHistory.length > 0 && (
              <div className="bg-gray-900/50 backdrop-blur border border-gray-700/50 rounded-xl shadow-xl p-6">
                <h3 className="text-lg font-semibold mb-4 text-white">Recent Analyses</h3>
                <div className="space-y-3">
                  {analysisHistory.map((item, idx) => (
                    <div key={idx} className="border-l-4 border-gray-500/50 pl-3 py-2">
                      <div className="text-sm text-gray-300 truncate">{item.text}</div>
                      <div className="text-xs text-gray-400 mt-1 flex items-center gap-1">
                        {item.result.is_claim ? "📊" : "💬"}
                        {item.result.is_claim ? "Claim detected" : "No claims"}
                        <span className="mx-1">•</span>
                        {item.timestamp.toLocaleTimeString()}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tips */}
            <div className="bg-gradient-to-br from-gray-900/50 to-gray-800/50 backdrop-blur border border-gray-600/30 rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-4 text-gray-300">💡 Pro Tips</h3>
              <ul className="space-y-2 text-sm text-gray-300">
                <li>• Try texts with specific statistics or numbers</li>
                <li>• Test health or scientific claims for best results</li>
                <li>• Compare different sources on the same topic</li>
                <li>• Watch for emotional or absolute language</li>
                <li>• Check the credibility assessment carefully</li>
              </ul>
            </div>

            {/* Health Check */}
            <div className="bg-gray-900/50 backdrop-blur border border-gray-700/50 rounded-xl shadow-xl p-4">
              <div className="space-y-2">
                <button 
                  onClick={async () => {
                    try {
                      const response = await fetch('http://localhost:8000/health');
                      const data = await response.json();
                      alert(`✅ Backend Status: ${data.status}\n🤖 Models: ${Object.keys(data.models_loaded).filter(k => data.models_loaded[k]).join(', ')}`);
                    } catch (error) {
                      alert(`❌ Backend Error: ${error.message}`);
                    }
                  }}
                  className="w-full text-sm bg-green-900/30 hover:bg-green-800/50 border border-green-500/30 text-green-300 p-2 rounded-lg transition-all backdrop-blur"
                >
                  🔧 Test Backend Connection
                </button>
                
                <button 
                  onClick={async () => {
                    try {
                      const response = await fetch('http://localhost:8000/analyze', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: 'Test message' })
                      });
                      
                      if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                      }
                      
                      const data = await response.json();
                      alert(`✅ Analyze Test Successful!\n📊 Is Claim: ${data.is_claim}\n📈 Confidence: ${(data.confidence * 100).toFixed(1)}%`);
                    } catch (error) {
                      alert(`❌ Analyze Test Failed: ${error.message}`);
                      console.error('Full error:', error);
                    }
                  }}
                  className="w-full text-sm bg-blue-900/30 hover:bg-blue-800/50 border border-blue-500/30 text-blue-300 p-2 rounded-lg transition-all backdrop-blur"
                >
                  🧪 Test Analyze Endpoint
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}