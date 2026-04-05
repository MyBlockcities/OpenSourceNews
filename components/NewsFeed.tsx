import React, { useState, useEffect } from 'react';
import { DailyReport, DailyFeedItem } from '../types';
import { YoutubeIcon } from './icons/YoutubeIcon';
import { RssIcon } from './icons/RssIcon';
import { GithubIcon } from './icons/GithubIcon';
import { HackerNewsIcon } from './icons/HackerNewsIcon';
import { LoadingSpinner } from './icons/LoadingSpinner';

interface FlatItem extends DailyFeedItem {
    topic: string;
    date: string;
}

const BUCKET_COLORS: Record<string, string> = {
    general: 'bg-blue-600/20 text-blue-400',
    ai: 'bg-purple-600/20 text-purple-400',
    blockchain: 'bg-orange-600/20 text-orange-400',
    sense_making: 'bg-emerald-600/20 text-emerald-400',
};

const BUCKET_LABELS: Record<string, string> = {
    general: 'General',
    ai: 'AI',
    blockchain: 'Blockchain',
    sense_making: 'Sense-Making',
};

const NewsFeed: React.FC = () => {
    const [allItems, setAllItems] = useState<FlatItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [filterBucket, setFilterBucket] = useState<string>('all');
    const [filterSource, setFilterSource] = useState<string>('all');
    const [searchQuery, setSearchQuery] = useState('');
    const [expandedItem, setExpandedItem] = useState<number | null>(null);

    useEffect(() => {
        loadNews();
    }, []);

    const loadNews = async () => {
        try {
            setLoading(true);
            const items: FlatItem[] = [];

            // Discover reports via API
            let dates: string[] = [];
            try {
                const resp = await fetch('/api/reports?limit=7');
                if (resp.ok) {
                    const data = await resp.json();
                    dates = (data.reports || []).map((r: { date: string }) => r.date);
                }
            } catch {
                // Fallback to recent dates
                const today = new Date();
                for (let i = 0; i < 7; i++) {
                    const d = new Date(today);
                    d.setDate(d.getDate() - i);
                    dates.push(d.toISOString().split('T')[0]);
                }
            }

            // Load each report
            for (const date of dates) {
                try {
                    let response = await fetch(`/daily/${date}.json`);
                    if (!response.ok) {
                        response = await fetch(`/api/reports/by-date/${date}`);
                        if (response.ok) {
                            const wrapper = await response.json();
                            flattenReport(wrapper.report, date, items);
                            continue;
                        }
                    }
                    if (response.ok) {
                        const report: DailyReport = await response.json();
                        flattenReport(report, date, items);
                    }
                } catch { /* skip */ }
            }

            setAllItems(items);
        } catch (error) {
            console.error('Failed to load news:', error);
        } finally {
            setLoading(false);
        }
    };

    const flattenReport = (report: DailyReport, date: string, items: FlatItem[]) => {
        for (const [topic, topicItems] of Object.entries(report)) {
            for (const item of topicItems) {
                items.push({ ...item, topic, date });
            }
        }
    };

    const getSourceIcon = (source: string) => {
        if (source === 'YouTube') return <YoutubeIcon className="w-4 h-4 flex-shrink-0" />;
        if (source === 'RSS') return <RssIcon className="w-4 h-4 flex-shrink-0" />;
        if (source === 'GitHub Trending') return <GithubIcon className="w-4 h-4 flex-shrink-0" />;
        if (source === 'Hacker News') return <HackerNewsIcon className="w-4 h-4 flex-shrink-0" />;
        return <RssIcon className="w-4 h-4 flex-shrink-0" />;
    };

    // Derive unique values for filters
    const buckets = [...new Set(allItems.map(i => i.bucket).filter(Boolean))] as string[];
    const sources = [...new Set(allItems.map(i => i.source).filter(Boolean))];

    // Apply filters
    const filtered = allItems.filter(item => {
        if (filterBucket !== 'all' && item.bucket !== filterBucket) return false;
        if (filterSource !== 'all' && item.source !== filterSource) return false;
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            return (
                (item.title || '').toLowerCase().includes(q) ||
                (item.summary || '').toLowerCase().includes(q) ||
                (item.topic || '').toLowerCase().includes(q)
            );
        }
        return true;
    });

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <LoadingSpinner className="w-8 h-8" />
                <span className="ml-3 text-gray-400">Loading news feed...</span>
            </div>
        );
    }

    return (
        <div className="animate-fade-in">
            <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-green-400 font-space-mono mb-2">
                    Open Source News Feed
                </h2>
                <p className="text-gray-400">{allItems.length} items from {new Set(allItems.map(i => i.date)).size} days</p>
            </div>

            {/* Filters */}
            <div className="bg-gray-800/30 rounded-lg p-4 mb-6 border border-gray-700 flex flex-wrap gap-3 items-center">
                <input
                    type="text"
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    placeholder="Search news..."
                    className="bg-gray-900 border border-gray-600 rounded-md px-3 py-2 text-gray-200 text-sm flex-grow min-w-[200px]"
                />
                <select
                    value={filterBucket}
                    onChange={e => setFilterBucket(e.target.value)}
                    className="bg-gray-900 border border-gray-600 rounded-md px-3 py-2 text-gray-200 text-sm"
                >
                    <option value="all">All Buckets</option>
                    {buckets.map(b => (
                        <option key={b} value={b}>{BUCKET_LABELS[b] || b}</option>
                    ))}
                </select>
                <select
                    value={filterSource}
                    onChange={e => setFilterSource(e.target.value)}
                    className="bg-gray-900 border border-gray-600 rounded-md px-3 py-2 text-gray-200 text-sm"
                >
                    <option value="all">All Sources</option>
                    {sources.map(s => (
                        <option key={s} value={s}>{s}</option>
                    ))}
                </select>
                <span className="text-gray-500 text-sm">{filtered.length} results</span>
            </div>

            {/* News Items */}
            {filtered.length === 0 ? (
                <div className="bg-gray-800/30 rounded-lg p-8 text-center border border-gray-700">
                    <p className="text-gray-400">No items match your filters.</p>
                    <p className="text-gray-500 text-sm mt-2">Try adjusting your search or run the daily pipeline.</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {filtered.map((item, idx) => (
                        <div
                            key={`${item.date}-${idx}`}
                            className="bg-gray-800/40 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors"
                        >
                            <div
                                className="p-4 cursor-pointer"
                                onClick={() => setExpandedItem(expandedItem === idx ? null : idx)}
                            >
                                <div className="flex items-start gap-3">
                                    {getSourceIcon(item.source)}
                                    <div className="flex-grow min-w-0">
                                        <div className="flex items-start justify-between gap-2 mb-1">
                                            <a
                                                href={item.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-cyan-400 hover:text-cyan-300 font-semibold transition-colors truncate"
                                                onClick={e => e.stopPropagation()}
                                            >
                                                {item.title}
                                            </a>
                                            <div className="flex items-center gap-2 flex-shrink-0">
                                                {item.quality_score != null && (
                                                    <span className="bg-cyan-600/20 text-cyan-400 text-xs font-bold px-2 py-0.5 rounded">
                                                        {item.quality_score}/10
                                                    </span>
                                                )}
                                                {item.bucket && (
                                                    <span className={`text-xs font-semibold px-2 py-0.5 rounded ${BUCKET_COLORS[item.bucket] || 'bg-gray-600/20 text-gray-400'}`}>
                                                        {BUCKET_LABELS[item.bucket] || item.bucket}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
                                            <span>{item.source}</span>
                                            <span>-</span>
                                            <span>{item.date}</span>
                                            {item.category && (
                                                <>
                                                    <span>-</span>
                                                    <span>{item.category}</span>
                                                </>
                                            )}
                                            {item.content_type && item.content_type !== 'General' && item.content_type !== 'news' && (
                                                <span className="bg-gray-700 px-1.5 py-0.5 rounded">{item.content_type}</span>
                                            )}
                                            {item.processing_mode && item.processing_mode !== 'standard_summary' && (
                                                <span className="bg-yellow-800/30 text-yellow-400 px-1.5 py-0.5 rounded">
                                                    {item.processing_mode === 'wisdom_extraction' ? 'Wisdom' : 'Claims'}
                                                </span>
                                            )}
                                        </div>
                                        {item.summary && (
                                            <p className="text-gray-400 text-sm mt-2 line-clamp-2">{item.summary}</p>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Expanded details */}
                            {expandedItem === idx && (
                                <div className="border-t border-gray-700 p-4 space-y-3">
                                    {item.key_insights && item.key_insights.length > 0 && (
                                        <div>
                                            <p className="text-xs font-semibold text-gray-400 mb-1">KEY INSIGHTS</p>
                                            {item.key_insights.map((insight, i) => (
                                                <p key={i} className="text-sm text-gray-300 pl-3 mb-1">- {insight}</p>
                                            ))}
                                        </div>
                                    )}
                                    {item.key_lessons && item.key_lessons.length > 0 && (
                                        <div>
                                            <p className="text-xs font-semibold text-gray-400 mb-1">KEY LESSONS</p>
                                            {item.key_lessons.map((lesson, i) => (
                                                <p key={i} className="text-sm text-gray-300 pl-3 mb-1">- {lesson}</p>
                                            ))}
                                        </div>
                                    )}
                                    {item.tools_mentioned && item.tools_mentioned.length > 0 && (
                                        <div>
                                            <p className="text-xs font-semibold text-gray-400 mb-1">TOOLS MENTIONED</p>
                                            <div className="flex flex-wrap gap-1">
                                                {item.tools_mentioned.map((tool, i) => (
                                                    <span key={i} className="bg-gray-700 text-gray-300 text-xs px-2 py-0.5 rounded">{tool}</span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {item.claims && item.claims.length > 0 && (
                                        <div>
                                            <p className="text-xs font-semibold text-gray-400 mb-1">CLAIMS ANALYSIS</p>
                                            <div className="space-y-2">
                                                {item.claims.map((claim, i) => (
                                                    <div key={i} className="bg-gray-900/50 rounded p-2 text-sm">
                                                        <p className="text-gray-200 font-medium">{claim.claim}</p>
                                                        <div className="flex items-center gap-2 mt-1 text-xs">
                                                            <span className={`px-1.5 py-0.5 rounded ${
                                                                claim.status === 'supported' ? 'bg-green-800/30 text-green-400' :
                                                                claim.status === 'contradicted' ? 'bg-red-800/30 text-red-400' :
                                                                claim.status === 'mixed' ? 'bg-yellow-800/30 text-yellow-400' :
                                                                'bg-gray-700 text-gray-400'
                                                            }`}>{claim.status}</span>
                                                            {claim.analyst_note && (
                                                                <span className="text-gray-500">{claim.analyst_note}</span>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {item.neutral_synthesis && (
                                        <div>
                                            <p className="text-xs font-semibold text-gray-400 mb-1">SYNTHESIS</p>
                                            <p className="text-sm text-gray-300 italic">{item.neutral_synthesis}</p>
                                        </div>
                                    )}
                                    {item.entities && item.entities.length > 0 && (
                                        <div className="flex flex-wrap gap-1">
                                            {item.entities.map((entity, i) => (
                                                <span key={i} className="bg-indigo-900/30 text-indigo-400 text-xs px-2 py-0.5 rounded">{entity}</span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default NewsFeed;
