import React, { useState, useEffect } from 'react';
import { DailyReport, DailyFeedItem, VideoScript } from '../types';
import { TopicIcon } from './icons/TopicIcon';
import { YoutubeIcon } from './icons/YoutubeIcon';
import { RssIcon } from './icons/RssIcon';
import { GithubIcon } from './icons/GithubIcon';
import { HackerNewsIcon } from './icons/HackerNewsIcon';
import { LoadingSpinner } from './icons/LoadingSpinner';
import { apiFetch } from '../services/apiClient';

const DailyFeedViewer: React.FC = () => {
    const [dailyReports, setDailyReports] = useState<{ date: string; data: DailyReport }[]>([]);
    const [selectedDate, setSelectedDate] = useState<string>('');
    const [selectedTopic, setSelectedTopic] = useState<string>('');
    const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
    const [loading, setLoading] = useState(true);
    const [generatingScript, setGeneratingScript] = useState(false);
    const [generatedScript, setGeneratedScript] = useState<VideoScript | null>(null);
    const [generatingAudio, setGeneratingAudio] = useState(false);
    const [audioUrl, setAudioUrl] = useState<string>('');

    // Load available daily reports
    useEffect(() => {
        loadDailyReports();
    }, []);

    const handleWeeklyAnalysis = () => {
        alert('📅 Weekly Analysis Feature\n\nTo generate a "This Week in AI" summary:\n\n1. Run in terminal:\n   python3 pipelines/weekly_analyzer.py\n\n2. This will analyze the past 7 days and create:\n   • Best nuggets extraction\n   • Emerging trends\n   • Actionable insights\n   • Weekly video script\n\n3. Output saved to:\n   outputs/weekly/YYYY-MM-DD-script.txt\n\nCost: ~$0.03 per week');
    };

    const loadDailyReports = async () => {
        try {
            setLoading(true);
            const reports: { date: string; data: DailyReport }[] = [];

            // Try API-based discovery first (uses /api/reports endpoint)
            let discoveredDates: string[] = [];
            try {
                const apiResp = await apiFetch('/api/reports?limit=14');
                if (apiResp.ok) {
                    const apiData = await apiResp.json();
                    discoveredDates = (apiData.reports || []).map((r: { date: string }) => r.date);
                    console.log(`✓ API discovered ${discoveredDates.length} reports`);
                }
            } catch {
                console.log('API unavailable, falling back to static file scan');
            }

            // Fallback: scan recent dates via static files if API returned nothing
            if (discoveredDates.length === 0) {
                const today = new Date();
                for (let i = 0; i < 14; i++) {
                    const d = new Date(today);
                    d.setDate(d.getDate() - i);
                    discoveredDates.push(d.toISOString().split('T')[0]);
                }
            }

            // Load each report (static files via publicDir or API)
            for (const date of discoveredDates) {
                try {
                    // Try static file first (faster, works without API running)
                    let response = await fetch(`/daily/${date}.json`);
                    if (!response.ok) {
                        // Fallback to API endpoint
                        response = await apiFetch(`/api/reports/by-date/${date}`);
                        if (response.ok) {
                            const wrapper = await response.json();
                            reports.push({ date, data: wrapper.report });
                            continue;
                        }
                    }
                    if (response.ok) {
                        const data = await response.json();
                        reports.push({ date, data });
                    }
                } catch {
                    // Silently skip dates without reports
                }
            }

            if (reports.length === 0) {
                console.warn('No reports found. Run python3 pipelines/daily_run.py to generate reports.');
            } else {
                console.log(`✓ Successfully loaded ${reports.length} daily reports`);
            }

            setDailyReports(reports);
            if (reports.length > 0) {
                setSelectedDate(reports[0].date);
                const topics = Object.keys(reports[0].data);
                if (topics.length > 0) {
                    setSelectedTopic(topics[0]);
                }
            }
        } catch (error) {
            console.error('Error loading daily reports:', error);
        } finally {
            setLoading(false);
        }
    };

    const toggleItemSelection = (index: number) => {
        const newSelected = new Set(selectedItems);
        if (newSelected.has(index)) {
            newSelected.delete(index);
        } else {
            newSelected.add(index);
        }
        setSelectedItems(newSelected);
    };

    const selectAll = () => {
        const allIndices = new Set(items.map((_, idx) => idx));
        setSelectedItems(allIndices);
    };

    const clearSelection = () => {
        setSelectedItems(new Set());
    };

    const handleGenerateScript = async () => {
        const selectedItemsArray = items.filter((_, idx) => selectedItems.has(idx));
        
        if (selectedItemsArray.length === 0) {
            alert('Please select at least one item to generate a script');
            return;
        }

        try {
            setGeneratingScript(true);
            setGeneratedScript(null);
            setAudioUrl('');

            const response = await apiFetch('/api/generate-script', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    items: selectedItemsArray,
                    topic: selectedTopic || 'Research',
                }),
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || 'Failed to generate script');
            }

            setGeneratedScript({
                script: result.script,
                sources: result.sources,
                metadata: {
                    generated_at: result.metadata?.generated_at || new Date().toISOString(),
                    num_sources: result.metadata?.num_sources || selectedItemsArray.length,
                    avg_quality_score: result.metadata?.avg_quality_score || 0,
                },
            });
            
        } catch (error) {
            console.error('Error generating script:', error);
            alert('Failed to generate script. Please try again.');
        } finally {
            setGeneratingScript(false);
        }
    };

    const handleGenerateAudio = async (scriptText: string) => {
        try {
            setGeneratingAudio(true);

            const response = await apiFetch('/api/generate-audio', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ script: scriptText, date: selectedDate }),
            });

            if (!response.ok) {
                throw new Error('Failed to generate audio');
            }

            const result = await response.json();
            setAudioUrl(result.audioUrl);
        } catch (error) {
            console.error('Error generating audio:', error);
            alert('Failed to generate audio. Please try again.');
        } finally {
            setGeneratingAudio(false);
        }
    };

    const getSourceIcon = (source: string) => {
        if (source === 'YouTube') return <YoutubeIcon className="w-4 h-4" />;
        if (source === 'RSS') return <RssIcon className="w-4 h-4" />;
        if (source === 'GitHub Trending') return <GithubIcon className="w-4 h-4" />;
        if (source === 'Hacker News') return <HackerNewsIcon className="w-4 h-4" />;
        return <RssIcon className="w-4 h-4" />;
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <LoadingSpinner className="w-8 h-8" />
                <span className="ml-3 text-gray-400">Loading daily reports...</span>
            </div>
        );
    }

    if (dailyReports.length === 0) {
        return (
            <div className="bg-gray-800/30 rounded-lg p-8 text-center border border-gray-700">
                <p className="text-gray-400 text-lg">No daily reports found.</p>
                <p className="text-gray-500 text-sm mt-2">Run the daily pipeline to generate reports.</p>
            </div>
        );
    }

    const currentReport = dailyReports.find(r => r.date === selectedDate);
    const topics = currentReport ? Object.keys(currentReport.data) : [];
    const items = currentReport && selectedTopic ? currentReport.data[selectedTopic] : [];

    return (
        <div className="animate-fade-in">
            <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-green-400 font-space-mono mb-2">
                    Daily Intelligence Feed
                </h2>
                <p className="text-gray-400">Review collected research and generate scripts on-demand</p>
            </div>

            {/* Date Selector */}
            <div className="bg-gray-800/30 rounded-lg p-4 mb-6 border border-gray-700">
                <label className="block text-sm font-semibold text-gray-400 mb-2">SELECT DATE</label>
                <select
                    value={selectedDate}
                    onChange={(e) => {
                        setSelectedDate(e.target.value);
                        setGeneratedScript(null);
                        setAudioUrl('');
                        const newReport = dailyReports.find(r => r.date === e.target.value);
                        if (newReport) {
                            const newTopics = Object.keys(newReport.data);
                            if (newTopics.length > 0) {
                                setSelectedTopic(newTopics[0]);
                            }
                        }
                    }}
                    className="bg-gray-900 border border-gray-600 rounded-md px-4 py-2 text-gray-200 w-full md:w-64"
                >
                    {dailyReports.map(report => (
                        <option key={report.date} value={report.date}>
                            {new Date(report.date).toLocaleDateString('en-US', { 
                                weekday: 'short', 
                                year: 'numeric', 
                                month: 'short', 
                                day: 'numeric' 
                            })}
                        </option>
                    ))}
                </select>
            </div>

            {/* Topic Tabs */}
            {topics.length > 0 && (
                <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
                    {topics.map(topic => (
                        <button
                            key={topic}
                            onClick={() => {
                                setSelectedTopic(topic);
                                setGeneratedScript(null);
                                setAudioUrl('');
                            }}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold whitespace-nowrap transition-colors ${
                                selectedTopic === topic
                                    ? 'bg-cyan-600 text-white'
                                    : 'bg-gray-800/50 text-gray-300 hover:bg-gray-700 border border-gray-700'
                            }`}
                        >
                            <TopicIcon className="w-4 h-4" />
                            {topic}
                            <span className="text-xs opacity-75">({currentReport?.data[topic]?.length || 0})</span>
                        </button>
                    ))}
                </div>
            )}

            {/* Feed Items */}
            <div className="bg-gray-800/30 rounded-lg p-6 mb-6 border border-gray-700">
                <div className="flex justify-between items-center mb-4">
                    <div className="flex items-center gap-4">
                        <h3 className="text-xl font-bold text-gray-200">
                            {items.length} Items
                        </h3>
                        {selectedItems.size > 0 && (
                            <span className="text-sm text-cyan-400 font-semibold">
                                ({selectedItems.size} selected)
                            </span>
                        )}
                    </div>
                    <div className="flex gap-2">
                        {items.length > 0 && (
                            <>
                                <button
                                    onClick={selectedItems.size === items.length ? clearSelection : selectAll}
                                    className="bg-gray-700 hover:bg-gray-600 text-white text-sm font-semibold px-3 py-2 rounded-md transition-colors"
                                >
                                    {selectedItems.size === items.length ? 'Clear All' : 'Select All'}
                                </button>
                                <button
                                    onClick={handleGenerateScript}
                                    disabled={generatingScript || selectedItems.size === 0}
                                    className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-semibold px-4 py-2 rounded-md transition-colors flex items-center gap-2"
                                >
                                    {generatingScript ? (
                                        <>
                                            <LoadingSpinner className="w-4 h-4" />
                                            Generating...
                                        </>
                                    ) : (
                                        `Generate Script (${selectedItems.size})`
                                    )}
                                </button>
                            </>
                        )}
                    </div>
                </div>

                {items.length === 0 ? (
                    <p className="text-gray-500 text-center py-8">No items for this topic.</p>
                ) : (
                    <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
                        {items.map((item, idx) => (
                            <div
                                key={idx}
                                className={`bg-gray-900/50 rounded-lg p-4 border transition-colors cursor-pointer ${
                                    selectedItems.has(idx)
                                        ? 'border-cyan-500 bg-cyan-900/10'
                                        : 'border-gray-700 hover:border-cyan-500/50'
                                }`}
                                onClick={() => toggleItemSelection(idx)}
                            >
                                <div className="flex items-start gap-3">
                                    {/* Checkbox */}
                                    <input
                                        type="checkbox"
                                        checked={selectedItems.has(idx)}
                                        onChange={() => toggleItemSelection(idx)}
                                        className="mt-1 w-4 h-4 accent-cyan-600 cursor-pointer"
                                        onClick={(e) => e.stopPropagation()}
                                    />
                                    {getSourceIcon(item.source)}
                                    <div className="flex-grow">
                                        <div className="flex items-start justify-between gap-2 mb-2">
                                            <a
                                                href={item.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-lg font-semibold text-cyan-400 hover:text-cyan-300 transition-colors"
                                            >
                                                {item.title}
                                            </a>
                                            {item.quality_score && (
                                                <span className="bg-cyan-600/20 text-cyan-400 text-xs font-bold px-2 py-1 rounded">
                                                    {item.quality_score}/10
                                                </span>
                                            )}
                                        </div>

                                        <div className="flex flex-wrap items-center gap-2 text-sm text-gray-400 mb-2">
                                            <span>{item.source}</span>
                                            {item.category && (
                                                <>
                                                    <span>·</span>
                                                    <span>{item.category}</span>
                                                </>
                                            )}
                                            {item.channelTitle && (
                                                <>
                                                    <span>·</span>
                                                    <span>{item.channelTitle}</span>
                                                </>
                                            )}
                                            {item.content_type && item.content_type !== 'General' && (
                                                <span className="bg-gray-700 px-2 py-0.5 rounded text-xs">
                                                    {item.content_type}
                                                </span>
                                            )}
                                            {item.target_audience && item.target_audience !== 'General' && (
                                                <span className="bg-gray-700 px-2 py-0.5 rounded text-xs">
                                                    {item.target_audience}
                                                </span>
                                            )}
                                        </div>

                                        {item.summary && (
                                            <p className="text-gray-300 text-sm mb-2">{item.summary}</p>
                                        )}

                                        {item.main_topic && (
                                            <p className="text-gray-400 text-sm italic mb-2">
                                                📌 {item.main_topic}
                                            </p>
                                        )}

                                        {item.key_insights && item.key_insights.length > 0 && (
                                            <div className="mt-2 space-y-1">
                                                <p className="text-xs font-semibold text-gray-400">KEY INSIGHTS:</p>
                                                {item.key_insights.map((insight, i) => (
                                                    <p key={i} className="text-sm text-gray-400 pl-3">
                                                        • {insight}
                                                    </p>
                                                ))}
                                            </div>
                                        )}

                                        {item.has_transcript && (
                                            <div className="mt-2 flex items-center gap-2 text-xs text-green-400">
                                                <span className="w-2 h-2 bg-green-400 rounded-full"></span>
                                                Transcript available ({item.transcript_word_count} words)
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Generated Script Display */}
            {generatedScript && (
                <div className="bg-gray-800/30 rounded-lg p-6 mb-6 border border-cyan-500">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-xl font-bold text-gray-200">Generated Script</h3>
                        <div className="flex gap-2">
                            <button
                                onClick={() => navigator.clipboard.writeText(generatedScript.script)}
                                className="bg-gray-700 hover:bg-gray-600 text-white font-semibold px-4 py-2 rounded-md transition-colors text-sm"
                            >
                                Copy Script
                            </button>
                            <button
                                onClick={() => handleGenerateAudio(generatedScript.script)}
                                disabled={generatingAudio}
                                className="bg-purple-600 hover:bg-purple-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-semibold px-4 py-2 rounded-md transition-colors text-sm flex items-center gap-2"
                            >
                                {generatingAudio ? (
                                    <>
                                        <LoadingSpinner className="w-4 h-4" />
                                        Generating Audio...
                                    </>
                                ) : (
                                    '🎙️ Generate Audio'
                                )}
                            </button>
                        </div>
                    </div>

                    {/* Script Metadata */}
                    <div className="flex gap-4 text-sm text-gray-400 mb-4 pb-4 border-b border-gray-700">
                        <span>📊 {generatedScript.metadata.num_sources} sources</span>
                        <span>⭐ Avg Quality: {generatedScript.metadata.avg_quality_score.toFixed(1)}/10</span>
                        <span>🕐 {new Date(generatedScript.metadata.generated_at).toLocaleString()}</span>
                    </div>

                    {/* Script Text */}
                    <div className="bg-gray-900/70 rounded-lg p-4 mb-4">
                        <pre className="text-sm text-gray-200 whitespace-pre-wrap font-mono leading-relaxed">
                            {generatedScript.script}
                        </pre>
                    </div>

                    {/* Sources Used */}
                    <details className="mt-4">
                        <summary className="text-sm font-semibold text-gray-400 cursor-pointer hover:text-cyan-400">
                            View Sources ({generatedScript.sources.length})
                        </summary>
                        <div className="mt-3 space-y-2">
                            {generatedScript.sources.map((source, idx) => (
                                <div key={idx} className="text-sm text-gray-400 pl-4">
                                    <a
                                        href={source.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-cyan-400 hover:text-cyan-300"
                                    >
                                        {idx + 1}. {source.title}
                                    </a>
                                    {source.quality_score && (
                                        <span className="ml-2 text-xs">({source.quality_score}/10)</span>
                                    )}
                                </div>
                            ))}
                        </div>
                    </details>
                </div>
            )}

            {/* Audio Player */}
            {audioUrl && (
                <div className="bg-gray-800/30 rounded-lg p-6 border border-purple-500">
                    <h3 className="text-xl font-bold text-gray-200 mb-4">Generated Audio</h3>
                    <audio controls className="w-full" src={audioUrl}>
                        Your browser does not support the audio element.
                    </audio>
                    <div className="mt-4 flex gap-2">
                        <a
                            href={audioUrl}
                            download
                            className="bg-purple-600 hover:bg-purple-500 text-white font-semibold px-4 py-2 rounded-md transition-colors text-sm"
                        >
                            Download Audio
                        </a>
                    </div>
                </div>
            )}

            {/* Info Panel */}
            <div className="bg-gray-800/20 rounded-lg p-4 border border-gray-700/50 mt-6">
                <h4 className="text-sm font-semibold text-gray-400 mb-2">💡 How It Works</h4>
                <ul className="text-sm text-gray-500 space-y-1">
                    <li>• Daily reports are collected automatically at 7 AM UTC</li>
                    <li>• Click "Generate Video Script" to create on-demand scripts using Gemini AI</li>
                    <li>• Click "Generate Audio" to convert scripts to speech using AssemblyAI</li>
                    <li>• Costs only apply when you generate scripts/audio (on-demand model)</li>
                </ul>
            </div>
        </div>
    );
};

export default DailyFeedViewer;
